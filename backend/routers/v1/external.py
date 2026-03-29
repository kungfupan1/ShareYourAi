"""
对外 API 路由 - 外部平台调用接口
"""
import time
import json
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db
from models import PlatformClient, PluginTask, PluginModel
from schemas import (
    ExternalTaskSubmit,
    ExternalTaskResponse,
    ExternalTaskQueryResponse,
    ExternalTaskDetail,
    ExternalAccountResponse,
    ExternalAccountInfo,
    ExternalModelsResponse,
    ExternalModelInfo
)
from middleware.api_key import get_authenticated_client, get_client_ip, APIKeyAuth
from services.billing import BillingService
from redis_client import redis_client
from engines.dispatcher import Dispatcher
from utils import generate_task_id


router = APIRouter(tags=["对外 API"])


@router.post("/tasks/submit", response_model=ExternalTaskResponse)
async def submit_task(
    request: Request,
    task_data: ExternalTaskSubmit,
    client: PlatformClient = Depends(get_authenticated_client),
    db: Session = Depends(get_db)
):
    """
    提交任务

    - model_id: 模型ID (grok_video, sora2_video, runway_video)
    - prompt: 提示词
    - images: 参考图片 (base64, 可选)
    - params: 生成参数 (可选)
    - callback_url: 回调地址 (可选)
    - external_id: 外部任务ID (可选)
    """
    start_time = time.time()
    billing = BillingService(db)
    ip_address = await get_client_ip(request)
    auth = APIKeyAuth(db)

    # 获取模型配置
    model = db.query(PluginModel).filter(
        PluginModel.model_id == task_data.model_id,
        PluginModel.is_active == True
    ).first()

    if not model:
        auth.log_call(
            client=client,
            action='submit',
            model_id=task_data.model_id,
            status='failed',
            ip_address=ip_address,
            user_agent=request.headers.get("user-agent"),
            error_message='Model not found'
        )
        return ExternalTaskResponse(
            success=False,
            error="Model not found",
            error_code="MODEL_NOT_FOUND"
        )

    # 检查余额
    if not billing.check_balance(client, model.user_price):
        auth.log_call(
            client=client,
            action='submit',
            model_id=task_data.model_id,
            status='failed',
            ip_address=ip_address,
            user_agent=request.headers.get("user-agent"),
            error_message='Insufficient balance'
        )
        return ExternalTaskResponse(
            success=False,
            error="Insufficient balance",
            error_code="INSUFFICIENT_BALANCE"
        )

    # 检查可用节点
    dispatcher = Dispatcher(db)
    available_nodes = dispatcher.get_available_nodes(task_data.model_id)

    if not available_nodes:
        auth.log_call(
            client=client,
            action='submit',
            model_id=task_data.model_id,
            status='failed',
            ip_address=ip_address,
            user_agent=request.headers.get("user-agent"),
            error_message='No available nodes'
        )
        return ExternalTaskResponse(
            success=False,
            error="No available nodes, please try again later",
            error_code="NO_AVAILABLE_NODES"
        )

    # 创建任务
    task_id = generate_task_id()
    task = PluginTask(
        task_id=task_id,
        model_id=task_data.model_id,
        prompt=task_data.prompt,
        images=json.dumps(task_data.images) if task_data.images else None,
        params=json.dumps(task_data.params) if task_data.params else None,
        source_system='external_api',
        source_client_id=client.client_id,
        source_order_id=task_data.external_id,
        status='pending',
        node_reward=model.node_reward,
        user_price=model.user_price
    )
    db.add(task)
    db.commit()

    # 预扣费
    billing.freeze_balance(client, model.user_price, task_id)

    # 推入队列
    redis_client.push_task(task_id)

    # 派单
    try:
        node = dispatcher.dispatch(task)
        if node:
            # 刷新任务状态
            db.refresh(task)

            # 推送任务给节点
            from websocket import push_task_to_node

            task_data_for_node = {
                "task_id": task.task_id,
                "model_id": task.model_id,
                "prompt": task.prompt,
                "images": json.loads(task.images) if task.images else None,
                "params": json.loads(task.params) if task.params else None,
                "page_url": model.page_url,
                "callback_url": task_data.callback_url
            }

            await push_task_to_node(node.node_id, task_data_for_node)
    except Exception as e:
        print(f"[External API] 派单失败: {e}")

    # 记录日志
    response_time = int((time.time() - start_time) * 1000)
    auth.log_call(
        client=client,
        action='submit',
        task_id=task_id,
        model_id=task_data.model_id,
        status='success',
        cost=model.user_price,
        ip_address=ip_address,
        user_agent=request.headers.get("user-agent"),
        request_params={"prompt": task_data.prompt[:100] if task_data.prompt else None},
        response_time=response_time
    )

    return ExternalTaskResponse(
        success=True,
        task_id=task_id,
        estimated_time=model.timeout,
        cost=model.user_price
    )


@router.get("/tasks/{task_id}", response_model=ExternalTaskQueryResponse)
async def get_task(
    request: Request,
    task_id: str,
    client: PlatformClient = Depends(get_authenticated_client),
    db: Session = Depends(get_db)
):
    """查询任务状态"""
    task = db.query(PluginTask).filter(
        PluginTask.task_id == task_id,
        PluginTask.source_client_id == client.client_id
    ).first()

    if not task:
        return ExternalTaskQueryResponse(
            success=False,
            error="Task not found",
            error_code="TASK_NOT_FOUND"
        )

    # 获取签名后的视频URL
    result_url = task.result_url
    if result_url and task.status == 'success':
        from routers.tasks import get_signed_video_url
        result_url = get_signed_video_url(result_url)

    task_detail = ExternalTaskDetail(
        task_id=task.task_id,
        status=task.status,
        model_id=task.model_id,
        prompt=task.prompt,
        result_url=result_url,
        duration=task.duration_seconds,
        file_size=task.file_size,
        created_at=task.create_time,
        completed_at=task.end_time
    )

    return ExternalTaskQueryResponse(
        success=True,
        task=task_detail
    )


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    request: Request,
    task_id: str,
    client: PlatformClient = Depends(get_authenticated_client),
    db: Session = Depends(get_db)
):
    """取消任务"""
    billing = BillingService(db)

    task = db.query(PluginTask).filter(
        PluginTask.task_id == task_id,
        PluginTask.source_client_id == client.client_id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status not in ['pending', 'processing']:
        raise HTTPException(status_code=400, detail="Task cannot be cancelled")

    # 取消任务
    old_status = task.status
    task.status = 'cancelled'
    task.end_time = datetime.now()
    db.commit()

    # 退款
    refund_amount = 0
    if old_status == 'pending':
        # 待处理任务，全额退款
        refund_amount = task.user_price
        billing.refund_frozen(client, refund_amount, task_id, "任务取消退款")

    return {
        "success": True,
        "message": "Task cancelled",
        "refund": refund_amount
    }


@router.get("/account/info", response_model=ExternalAccountResponse)
async def get_account_info(
    client: PlatformClient = Depends(get_authenticated_client)
):
    """查询账户信息"""
    return ExternalAccountResponse(
        success=True,
        account=ExternalAccountInfo(
            client_id=client.client_id,
            client_name=client.client_name,
            balance=client.balance,
            frozen_balance=client.frozen_balance,
            total_calls=client.total_calls,
            total_spent=client.total_spent
        )
    )


@router.get("/models", response_model=ExternalModelsResponse)
async def get_models(
    client: PlatformClient = Depends(get_authenticated_client),
    db: Session = Depends(get_db)
):
    """获取可用模型列表"""
    models = db.query(PluginModel).filter(
        PluginModel.is_active == True
    ).all()

    model_list = []
    for m in models:
        model_info = ExternalModelInfo(
            model_id=m.model_id,
            name=m.name,
            description=f"{m.provider} {m.model_type}",
            price=m.user_price,
            params={
                "duration": {"min": 1, "max": 60, "default": 5},
                "aspect_ratio": ["1:1", "16:9", "9:16"],
                "resolution": ["480p", "720p", "1080p"]
            }
        )
        model_list.append(model_info)

    return ExternalModelsResponse(
        success=True,
        models=model_list
    )