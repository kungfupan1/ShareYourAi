"""
任务管理路由
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, UploadFile, File
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
import json

from database import get_db
from models import PluginTask, PluginModel, PluginNode, PluginUser, PluginStorageBucket
from schemas import (
    TaskSubmit, TaskResult, TaskResponse,
    MessageResponse
)
from routers.auth import get_current_user
from utils import generate_task_id
from redis_client import redis_client
from engines.dispatcher import Dispatcher

router = APIRouter(prefix="/api/tasks", tags=["任务管理"])


def get_signed_video_url(result_url: str, expire_seconds: int = 3600) -> str:
    """
    获取视频的签名访问 URL
    如果是 COS 存储，生成签名 URL
    如果是本地存储，返回相对路径
    """
    if not result_url:
        return None

    # 本地存储
    if result_url.startswith("/api/"):
        return result_url

    # COS 存储（cos://bucket/key 格式）
    if result_url.startswith("cos://"):
        from services.cos_service import get_cos_service
        cos_service = get_cos_service()
        if cos_service:
            # 解析 cos://bucket/key
            parts = result_url[6:].split("/", 1)
            if len(parts) == 2:
                bucket, key = parts
                signed_url = cos_service.get_signed_url(key, expire_seconds)
                if signed_url:
                    return signed_url
        # 如果签名失败，尝试直接返回
        return result_url

    # 已经是 HTTP URL（可能是旧的直接 URL）
    if result_url.startswith("http"):
        return result_url

    return result_url


def process_task_dispatch(task_id: str, db_url: str):
    """后台任务：派单处理"""
    from database import SessionLocal
    import asyncio
    db = SessionLocal()
    try:
        task = db.query(PluginTask).filter(PluginTask.task_id == task_id).first()
        if not task:
            return

        # 获取模型配置
        model = db.query(PluginModel).filter(PluginModel.model_id == task.model_id).first()
        if not model:
            task.status = 'failed'
            task.error_message = "模型配置不存在"
            db.commit()
            return

        # 派单
        dispatcher = Dispatcher(db)
        node = dispatcher.dispatch(task)

        if not node:
            # 无可用节点，放回队列
            task.status = 'pending'
            db.commit()
            redis_client.push_task(task_id)
            print(f"[派单] 任务 {task_id} 无可用节点，已放回队列")
            return

        # 推送任务给节点（通过 WebSocket）
        from websocket import push_task_to_node

        task_data = {
            "task_id": task.task_id,
            "model_id": task.model_id,
            "prompt": task.prompt,
            "images": json.loads(task.images) if task.images else None,
            "params": json.loads(task.params) if task.params else None,
            "page_url": model.page_url
        }

        # 推送任务（使用 asyncio.run 在后台线程中执行异步函数）
        try:
            asyncio.run(push_task_to_node(node.node_id, task_data))
            print(f"[派单] 任务 {task_id} 已推送给节点 {node.node_id}")
        except Exception as e:
            print(f"[派单] 推送任务失败: {e}")
            # 放回队列
            task.status = 'pending'
            task.assigned_node_id = None
            db.commit()
            redis_client.push_task(task_id)

    except Exception as e:
        print(f"[派单] 派单异常: {e}")
    finally:
        db.close()


@router.post("/submit", response_model=MessageResponse)
async def submit_task(
        task_data: TaskSubmit,
        user: PluginUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """提交任务"""
    # 检查模型是否存在
    model = db.query(PluginModel).filter(
        PluginModel.model_id == task_data.model_id,
        PluginModel.is_active == True
    ).first()

    if not model:
        raise HTTPException(status_code=400, detail="模型不存在或已禁用")

    # 生成任务 ID
    task_id = generate_task_id()

    # 创建任务
    task = PluginTask(
        task_id=task_id,
        user_id=user.id,
        model_id=task_data.model_id,
        prompt=task_data.prompt,
        images=json.dumps(task_data.images) if task_data.images else None,
        params=json.dumps(task_data.params) if task_data.params else None,
        source_system=task_data.source_system,
        source_user_id=task_data.source_user_id,
        source_order_id=task_data.source_order_id,
        status='pending',
        node_reward=model.node_reward,
        user_price=model.user_price
    )

    db.add(task)
    db.commit()

    # 推入队列
    redis_client.push_task(task_id)

    # 更新统计
    redis_client.incr_daily_stat("tasks_submitted")

    # 直接在请求中执行派单（而不是后台任务，这样才能访问 WebSocket）
    try:
        # 先刷新确保获取最新数据
        db.refresh(task)

        dispatcher = Dispatcher(db)
        print(f"[派单] 开始派单，任务 {task_id}")

        node = dispatcher.dispatch(task)
        print(f"[派单] dispatch 返回: {node.node_id if node else None}")

        if node:
            # 刷新任务状态
            db.refresh(task)
            print(f"[派单] 任务状态: {task.status}, 节点: {task.assigned_node_id}")

            # 推送任务给节点
            from websocket import push_task_to_node

            task_data_for_node = {
                "task_id": task.task_id,
                "model_id": task.model_id,
                "prompt": task.prompt,
                "images": json.loads(task.images) if task.images else None,
                "params": json.loads(task.params) if task.params else None,
                "page_url": model.page_url
            }

            await push_task_to_node(node.node_id, task_data_for_node)
            print(f"[派单] 任务 {task_id} 已推送给节点 {node.node_id}")
        else:
            print(f"[派单] 任务 {task_id} 无可用节点，已放入队列")
    except Exception as e:
        import traceback
        print(f"[派单] 派单失败: {e}")
        traceback.print_exc()

    return MessageResponse(
        success=True,
        message="任务已提交",
        data={"task_id": task_id}
    )


@router.get("/upload-credential")
async def get_upload_credential(
        task_id: str,
        user: PluginUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    获取视频上传预签名URL（前端直传COS）

    返回预签名PUT URL，Content Script可直接上传Blob到COS
    """
    from models import PluginStorageBucket
    from services.cos_service import get_cos_service, init_cos_service

    # 查找任务
    task = db.query(PluginTask).filter(PluginTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 验证任务归属
    node = db.query(PluginNode).filter(
        PluginNode.user_id == user.id,
        PluginNode.node_id == task.assigned_node_id
    ).first()
    if not node:
        raise HTTPException(status_code=403, detail="无权操作此任务")

    # 获取存储桶配置
    bucket_config = db.query(PluginStorageBucket).filter(
        PluginStorageBucket.is_default == True
    ).first()

    if not bucket_config:
        raise HTTPException(status_code=500, detail="未配置存储桶")

    # 初始化 COS 服务
    cos_service = get_cos_service()
    if not cos_service:
        init_cos_service(
            bucket_config.secret_id,
            bucket_config.secret_key,
            bucket_config.bucket_name,
            bucket_config.region
        )
        cos_service = get_cos_service()

    if not cos_service:
        raise HTTPException(status_code=500, detail="COS服务初始化失败")

    # 生成存储路径
    from datetime import datetime
    now = datetime.now()
    date_path = now.strftime("%Y/%m")
    key = f"tasks/videos/{date_path}/{task_id}.mp4"

    # 获取预签名PUT URL
    credential = cos_service.get_presigned_put_url(
        key=key,
        content_type='video/mp4',
        expire_seconds=3600
    )

    if not credential:
        raise HTTPException(status_code=500, detail="生成上传凭证失败")

    return {
        "success": True,
        "presigned_url": credential['presigned_url'],
        "result_url": credential['result_url'],
        "content_type": "video/mp4",
        "expires_at": credential['expires_at']
    }


@router.post("/upload/{task_id}")
async def upload_video(
        task_id: str,
        file: UploadFile = File(...),
        user: PluginUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """代理上传视频到 COS（解决 CORS 问题）"""
    from services.cos_service import get_cos_service, init_cos_service
    from models import PluginStorageBucket

    task = db.query(PluginTask).filter(PluginTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 验证任务归属
    node = db.query(PluginNode).filter(
        PluginNode.user_id == user.id,
        PluginNode.node_id == task.assigned_node_id
    ).first()
    if not node:
        raise HTTPException(status_code=403, detail="无权操作此任务")

    # 获取文件内容
    content = await file.read()
    file_size = len(content)

    # 获取存储桶配置
    bucket_config = db.query(PluginStorageBucket).filter(
        PluginStorageBucket.is_default == True
    ).first()

    # 延迟初始化 COS 服务
    cos_service = get_cos_service()
    if not cos_service and bucket_config:
        init_cos_service(bucket_config.secret_id, bucket_config.secret_key,
                        bucket_config.bucket_name, bucket_config.region)
        cos_service = get_cos_service()

    if cos_service and bucket_config:
        # 上传到 COS
        key = f"tasks/videos/{task_id}.mp4"
        try:
            print(f"[上传] 开始上传到 COS: {bucket_config.bucket_name}, key: {key}, size: {file_size}")
            cos_service.client.put_object(
                Bucket=bucket_config.bucket_name,
                Key=key,
                Body=content
            )
            # 存储 key 而不是直接 URL，便于后续生成签名
            result_url = f"cos://{bucket_config.bucket_name}/{key}"
            print(f"[上传] COS 上传成功: {result_url}")
        except Exception as e:
            # COS 上传失败，使用本地存储
            print(f"[上传] COS 上传失败: {e}")
            import os
            upload_dir = "uploads/videos"
            os.makedirs(upload_dir, exist_ok=True)
            file_path = os.path.join(upload_dir, f"{task_id}.mp4")
            with open(file_path, "wb") as f:
                f.write(content)
            result_url = f"/api/tasks/download/{task_id}"
            print(f"[上传] 已保存到本地: {file_path}")
    else:
        # 没有配置 COS，保存到本地（开发环境）
        import os
        upload_dir = "uploads/videos"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f"{task_id}.mp4")
        with open(file_path, "wb") as f:
            f.write(content)
        result_url = f"/api/tasks/download/{task_id}"
        print(f"[上传] 无 COS 配置，保存到本地: {file_path}")

    # 更新任务
    task.result_url = result_url
    task.file_size = file_size
    task.file_format = "mp4"
    task.status = 'success'
    task.end_time = datetime.now()
    task.images = None  # 清空图片数据，释放数据库空间

    if task.start_time:
        task.duration_seconds = int((task.end_time - task.start_time).total_seconds())

    db.commit()

    # 释放节点（上传成功即视为任务完成）
    if task.assigned_node_id:
        from engines.dispatcher import Dispatcher
        dispatcher = Dispatcher(db)
        dispatcher.release_node(task.assigned_node_id)
        print(f"[上传] 节点已释放: {task.assigned_node_id}")

    return {
        "success": True,
        "result_url": result_url,
        "file_size": file_size
    }


@router.get("/download/{task_id}")
async def download_video(
        task_id: str,
        db: Session = Depends(get_db)
):
    """下载视频（带签名）"""
    from fastapi.responses import FileResponse, RedirectResponse

    task = db.query(PluginTask).filter(PluginTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 检查本地文件
    import os
    file_path = os.path.join("uploads/videos", f"{task_id}.mp4")
    if os.path.exists(file_path):
        return FileResponse(
            file_path,
            media_type="video/mp4",
            filename=f"{task_id}.mp4"
        )

    # COS 存储，生成签名 URL 重定向
    if task.result_url:
        signed_url = get_signed_video_url(task.result_url, expire_seconds=3600)
        if signed_url and signed_url.startswith("http"):
            return RedirectResponse(url=signed_url)

    raise HTTPException(status_code=404, detail="视频文件不存在")


@router.post("/result", response_model=MessageResponse)
async def submit_task_result(
        result: TaskResult,
        user: PluginUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """提交任务结果（插件调用）"""
    # 查找任务
    task = db.query(PluginTask).filter(PluginTask.task_id == result.task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 如果任务已经通过上传接口完成，跳过处理
    if task.status == 'success':
        return MessageResponse(
            success=True,
            message=f"任务已完成（通过上传接口），状态: {task.status}"
        )

    # 验证节点归属
    node = db.query(PluginNode).filter(
        PluginNode.node_id == result.node_id,
        PluginNode.user_id == user.id
    ).first()

    if not node:
        raise HTTPException(status_code=403, detail="无权操作此任务")

    if task.assigned_node_id != result.node_id:
        raise HTTPException(status_code=400, detail="任务未分配给此节点")

    # 更新任务状态
    task.status = result.status
    task.result_url = result.result_url
    task.error_message = result.error_message
    task.end_time = datetime.now()
    task.images = None  # 清空图片数据，释放数据库空间

    if task.start_time:
        task.duration_seconds = int((task.end_time - task.start_time).total_seconds())

    # 保存证据数据
    if result.proof:
        task.proof_data = json.dumps(result.proof, ensure_ascii=False)

    # 保存文件信息
    if result.file_size:
        task.file_size = result.file_size
    if result.file_format:
        task.file_format = result.file_format

    db.commit()

    # 获取 dispatcher
    from engines.dispatcher import Dispatcher
    dispatcher = Dispatcher(db)

    # 如果成功，执行校验
    if result.status == 'success':
        from engines.validator import TaskValidator
        validator = TaskValidator(db)
        validation_result = validator.validate(task, result.proof or {})

        if validation_result.passed:
            # 校验通过，进入待审核状态
            task.earning_status = 'auditing'

            # 更新用户冻结余额
            user_obj = db.query(PluginUser).filter(PluginUser.id == task.user_id).first()
            if user_obj:
                user_obj.frozen_auditing = (user_obj.frozen_auditing or 0) + (task.node_reward or 0)

            # 更新节点统计
            dispatcher.update_node_score(
                result.node_id,
                success=True,
                duration=task.duration_seconds or 0,
                reward=task.node_reward or 0.07
            )

            redis_client.incr_daily_stat("tasks_completed")
        else:
            # 校验失败
            task.earning_status = 'cancelled'

            # 更新节点统计
            dispatcher.update_node_score(
                result.node_id,
                success=False,
                duration=0
            )

        # 释放节点（无论校验成功还是失败）
        dispatcher.release_node(result.node_id)
    else:
        # 任务失败
        task.earning_status = 'cancelled'

        # 释放节点
        dispatcher.release_node(result.node_id)
        dispatcher.update_node_score(
            result.node_id,
            success=False,
            duration=0
        )

    db.commit()

    return MessageResponse(
        success=True,
        message=f"任务结果已更新: {result.status}"
    )


@router.get("/status/{task_id}")
async def get_task_status(
        task_id: str,
        user: PluginUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """获取任务状态（轻量接口，供插件轮询）"""
    task = db.query(PluginTask).filter(PluginTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    return {
        "task_id": task.task_id,
        "status": task.status
    }


@router.get("/list", response_model=List[TaskResponse])
async def list_tasks(
        status: Optional[str] = None,
        limit: int = 20,
        user: PluginUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """获取用户的任务列表"""
    query = db.query(PluginTask).filter(PluginTask.user_id == user.id)

    if status:
        query = query.filter(PluginTask.status == status)

    tasks = query.order_by(PluginTask.create_time.desc()).limit(limit).all()

    return [TaskResponse.from_orm(t) for t in tasks]


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
        task_id: str,
        user: PluginUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """获取任务详情"""
    task = db.query(PluginTask).filter(
        PluginTask.task_id == task_id,
        PluginTask.user_id == user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    return TaskResponse.from_orm(task)


@router.post("/{task_id}/start", response_model=MessageResponse)
async def start_task(
        task_id: str,
        node_id: str,
        user: PluginUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """开始执行任务（插件调用）"""
    task = db.query(PluginTask).filter(PluginTask.task_id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 验证节点
    node = db.query(PluginNode).filter(
        PluginNode.node_id == node_id,
        PluginNode.user_id == user.id
    ).first()

    if not node:
        raise HTTPException(status_code=403, detail="无权操作此节点")

    if task.assigned_node_id != node_id:
        raise HTTPException(status_code=400, detail="任务未分配给此节点")

    # 更新任务状态
    task.status = 'processing'
    task.start_time = datetime.now()

    db.commit()

    return MessageResponse(success=True, message="任务已开始")


# 外部接口（供 Hi-Tom-AI 调用）
@router.post("/external/submit", response_model=MessageResponse)
async def external_submit_task(
        task_data: TaskSubmit,
        api_key: str,
        db: Session = Depends(get_db)
):
    """外部系统提交任务"""
    from models import PluginSystemConfig

    # 验证 API Key
    config = db.query(PluginSystemConfig).filter(
        PluginSystemConfig.config_key == 'external_api_key'
    ).first()

    if not config or config.config_value != api_key:
        raise HTTPException(status_code=401, detail="API Key 无效")

    # 检查模型
    model = db.query(PluginModel).filter(
        PluginModel.model_id == task_data.model_id,
        PluginModel.is_active == True
    ).first()

    if not model:
        raise HTTPException(status_code=400, detail="模型不存在或已禁用")

    # 生成任务 ID
    task_id = generate_task_id()

    # 创建任务
    task = PluginTask(
        task_id=task_id,
        model_id=task_data.model_id,
        prompt=task_data.prompt,
        images=json.dumps(task_data.images) if task_data.images else None,
        params=json.dumps(task_data.params) if task_data.params else None,
        source_system=task_data.source_system or 'external',
        source_user_id=task_data.source_user_id,
        source_order_id=task_data.source_order_id,
        status='pending',
        node_reward=model.node_reward,
        user_price=model.user_price
    )

    db.add(task)
    db.commit()

    # 推入队列
    redis_client.push_task(task_id)

    return MessageResponse(
        success=True,
        message="任务已提交",
        data={"task_id": task_id}
    )


@router.get("/external/status/{task_id}")
async def get_external_task_status(
        task_id: str,
        api_key: str,
        db: Session = Depends(get_db)
):
    """外部系统查询任务状态"""
    from models import PluginSystemConfig

    # 验证 API Key
    config = db.query(PluginSystemConfig).filter(
        PluginSystemConfig.config_key == 'external_api_key'
    ).first()

    if not config or config.config_value != api_key:
        raise HTTPException(status_code=401, detail="API Key 无效")

    task = db.query(PluginTask).filter(PluginTask.task_id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    return {
        "task_id": task.task_id,
        "status": task.status,
        "result_url": get_signed_video_url(task.result_url) if task.status == 'success' else None,
        "error_message": task.error_message,
        "duration": task.duration_seconds
    }


# 测试接口：检查节点状态
@router.get("/debug/nodes")
async def debug_nodes(
        db: Session = Depends(get_db)
):
    """调试：检查节点状态"""
    from redis_client import redis_client
    from models import PluginUser

    nodes = db.query(PluginNode).join(
        PluginUser, PluginNode.user_id == PluginUser.id
    ).filter(
        PluginNode.status == 'idle',
        PluginUser.is_blacklisted == False
    ).all()

    result = []
    for node in nodes:
        ws = redis_client.get_ws_session(node.node_id)
        result.append({
            "node_id": node.node_id,
            "db_status": node.status,
            "ws_session": ws
        })

    return {"nodes": result}


# 测试接口：手动派单
@router.post("/test-dispatch/{task_id}")
async def test_dispatch(
        task_id: str,
        db: Session = Depends(get_db)
):
    """手动触发派单（测试用）"""
    task = db.query(PluginTask).filter(PluginTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 检查可用节点
    dispatcher = Dispatcher(db)
    available_nodes = dispatcher.get_available_nodes(task.model_id)

    if not available_nodes:
        return {
            "success": False,
            "message": "没有可用节点",
            "task_status": task.status,
            "nodes_checked": True
        }

    # 派单
    node = dispatcher.dispatch(task)

    if node:
        # 获取模型配置
        model = db.query(PluginModel).filter(PluginModel.model_id == task.model_id).first()

        # 推送任务
        from websocket import push_task_to_node

        task_data = {
            "task_id": task.task_id,
            "model_id": task.model_id,
            "prompt": task.prompt,
            "images": json.loads(task.images) if task.images else None,
            "params": json.loads(task.params) if task.params else None,
            "page_url": model.page_url if model else None
        }

        await push_task_to_node(node.node_id, task_data)

        return {
            "success": True,
            "message": f"任务已分配给节点 {node.node_id}",
            "node_id": node.node_id,
            "task_data": task_data
        }
    else:
        return {
            "success": False,
            "message": "派单失败"
        }