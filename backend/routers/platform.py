"""
平台客户管理 API - 管理后台使用
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, List
import json

from database import get_db
from models import PlatformClient, ClientTransaction, ClientCallLog, PluginTask
from schemas import (
    PlatformClientCreate,
    PlatformClientUpdate,
    PlatformClientResponse,
    PlatformClientDetail,
    BalanceAdjustRequest,
    RechargeRequest,
    ClientTransactionResponse,
    ClientCallLogResponse,
    MessageResponse
)
from middleware.api_key import mask_api_key
from services.billing import BillingService
from utils import generate_client_id, generate_api_key


router = APIRouter(prefix="/api/admin/platforms", tags=["平台客户管理"])


@router.get("")
async def list_platforms(
    user_id: int,
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取平台客户列表"""
    query = db.query(PlatformClient)

    if keyword:
        query = query.filter(
            (PlatformClient.client_name.contains(keyword)) |
            (PlatformClient.client_id.contains(keyword))
        )

    if status:
        query = query.filter(PlatformClient.status == status)

    total = query.count()
    clients = query.order_by(PlatformClient.create_time.desc()).offset((page - 1) * page_size).limit(page_size).all()

    # 脱敏 API Key
    for client in clients:
        client.api_key = mask_api_key(client.api_key)

    return {
        "data": clients,
        "total": total
    }


@router.post("", response_model=MessageResponse)
async def create_platform(
    user_id: int,
    data: PlatformClientCreate,
    db: Session = Depends(get_db)
):
    """创建平台客户"""
    client = PlatformClient(
        client_id=generate_client_id(),
        client_name=data.client_name,
        api_key=generate_api_key(),
        contact_name=data.contact_name,
        contact_phone=data.contact_phone,
        contact_email=data.contact_email,
        callback_url=data.callback_url,
        ip_whitelist=json.dumps(data.ip_whitelist) if data.ip_whitelist else None
    )

    db.add(client)
    db.commit()

    return MessageResponse(
        success=True,
        message="平台客户创建成功",
        data={
            "client_id": client.client_id,
            "api_key": client.api_key  # 创建时返回完整 API Key
        }
    )


@router.get("/{client_id}", response_model=PlatformClientDetail)
async def get_platform(
    client_id: str,
    user_id: int,
    db: Session = Depends(get_db)
):
    """获取平台客户详情"""
    client = db.query(PlatformClient).filter(
        PlatformClient.client_id == client_id
    ).first()

    if not client:
        raise HTTPException(status_code=404, detail="平台客户不存在")

    # 解析 IP 白名单
    ip_whitelist = None
    if client.ip_whitelist:
        try:
            ip_whitelist = json.loads(client.ip_whitelist)
        except:
            pass

    return PlatformClientDetail(
        id=client.id,
        client_id=client.client_id,
        client_name=client.client_name,
        api_key=mask_api_key(client.api_key),
        balance=client.balance,
        frozen_balance=client.frozen_balance,
        contact_name=client.contact_name,
        contact_phone=client.contact_phone,
        contact_email=client.contact_email,
        status=client.status,
        total_calls=client.total_calls,
        total_spent=client.total_spent,
        total_recharged=client.total_recharged,
        callback_url=client.callback_url,
        ip_whitelist=ip_whitelist,
        create_time=client.create_time
    )


@router.put("/{client_id}", response_model=MessageResponse)
async def update_platform(
    client_id: str,
    user_id: int,
    data: PlatformClientUpdate,
    db: Session = Depends(get_db)
):
    """更新平台客户"""
    client = db.query(PlatformClient).filter(
        PlatformClient.client_id == client_id
    ).first()

    if not client:
        raise HTTPException(status_code=404, detail="平台客户不存在")

    if data.client_name is not None:
        client.client_name = data.client_name
    if data.contact_name is not None:
        client.contact_name = data.contact_name
    if data.contact_phone is not None:
        client.contact_phone = data.contact_phone
    if data.contact_email is not None:
        client.contact_email = data.contact_email
    if data.callback_url is not None:
        client.callback_url = data.callback_url
    if data.ip_whitelist is not None:
        client.ip_whitelist = json.dumps(data.ip_whitelist)
    if data.status is not None:
        client.status = data.status

    db.commit()

    return MessageResponse(success=True, message="更新成功")


@router.post("/{client_id}/recharge", response_model=MessageResponse)
async def recharge_platform(
    client_id: str,
    user_id: int,
    data: RechargeRequest,
    db: Session = Depends(get_db)
):
    """平台充值"""
    client = db.query(PlatformClient).filter(
        PlatformClient.client_id == client_id
    ).first()

    if not client:
        raise HTTPException(status_code=404, detail="平台客户不存在")

    billing = BillingService(db)
    success = billing.recharge(client, data.amount, operator_id=user_id, remark=data.remark)

    if not success:
        raise HTTPException(status_code=400, detail="充值失败")

    return MessageResponse(
        success=True,
        message="充值成功",
        data={"balance": client.balance}
    )


@router.post("/{client_id}/adjust", response_model=MessageResponse)
async def adjust_platform_balance(
    client_id: str,
    user_id: int,
    data: BalanceAdjustRequest,
    db: Session = Depends(get_db)
):
    """调整平台余额"""
    client = db.query(PlatformClient).filter(
        PlatformClient.client_id == client_id
    ).first()

    if not client:
        raise HTTPException(status_code=404, detail="平台客户不存在")

    billing = BillingService(db)
    amount = data.amount if data.adjust_type == 'add' else -data.amount

    success = billing.adjust_balance(client, amount, operator_id=user_id, remark=data.remark)

    if not success:
        raise HTTPException(status_code=400, detail="调整失败")

    return MessageResponse(
        success=True,
        message="调整成功",
        data={"balance": client.balance}
    )


@router.post("/{client_id}/reset-key", response_model=MessageResponse)
async def reset_api_key(
    client_id: str,
    user_id: int,
    db: Session = Depends(get_db)
):
    """重置 API Key"""
    client = db.query(PlatformClient).filter(
        PlatformClient.client_id == client_id
    ).first()

    if not client:
        raise HTTPException(status_code=404, detail="平台客户不存在")

    client.api_key = generate_api_key()
    db.commit()

    return MessageResponse(
        success=True,
        message="API Key 已重置",
        data={"api_key": client.api_key}
    )


@router.get("/{client_id}/transactions", response_model=List[ClientTransactionResponse])
async def list_transactions(
    client_id: str,
    user_id: int,
    page: int = 1,
    page_size: int = 20,
    trans_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取交易记录"""
    query = db.query(ClientTransaction).filter(
        ClientTransaction.client_id == client_id
    )

    if trans_type:
        query = query.filter(ClientTransaction.type == trans_type)

    transactions = query.order_by(ClientTransaction.create_time.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return transactions


@router.get("/{client_id}/call-logs", response_model=List[ClientCallLogResponse])
async def list_call_logs(
    client_id: str,
    user_id: int,
    page: int = 1,
    page_size: int = 20,
    action: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取调用日志"""
    query = db.query(ClientCallLog).filter(
        ClientCallLog.client_id == client_id
    )

    if action:
        query = query.filter(ClientCallLog.action == action)
    if status:
        query = query.filter(ClientCallLog.status == status)

    logs = query.order_by(ClientCallLog.create_time.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return logs


@router.get("/{client_id}/tasks")
async def list_client_tasks(
    client_id: str,
    user_id: int,
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取平台的任务列表"""
    query = db.query(PluginTask).filter(
        PluginTask.source_client_id == client_id
    )

    if status:
        query = query.filter(PluginTask.status == status)

    tasks = query.order_by(PluginTask.create_time.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return [
        {
            "task_id": t.task_id,
            "model_id": t.model_id,
            "status": t.status,
            "prompt": t.prompt[:50] + '...' if t.prompt and len(t.prompt) > 50 else t.prompt,
            "user_price": t.user_price,
            "duration": t.duration_seconds,
            "create_time": t.create_time
        }
        for t in tasks
    ]


@router.get("/{client_id}/stats")
async def get_client_stats(
    client_id: str,
    user_id: int,
    db: Session = Depends(get_db)
):
    """获取平台统计信息"""
    client = db.query(PlatformClient).filter(
        PlatformClient.client_id == client_id
    ).first()

    if not client:
        raise HTTPException(status_code=404, detail="平台客户不存在")

    # 今日统计
    from utils import get_today_str
    today = get_today_str()

    today_tasks = db.query(PluginTask).filter(
        PluginTask.source_client_id == client_id,
        PluginTask.create_time >= datetime.strptime(today, "%Y-%m-%d")
    ).count()

    today_success = db.query(PluginTask).filter(
        PluginTask.source_client_id == client_id,
        PluginTask.create_time >= datetime.strptime(today, "%Y-%m-%d"),
        PluginTask.status == 'success'
    ).count()

    return {
        "total_calls": client.total_calls,
        "total_spent": client.total_spent,
        "balance": client.balance,
        "frozen_balance": client.frozen_balance,
        "today_tasks": today_tasks,
        "today_success": today_success,
        "success_rate": round(today_success / today_tasks * 100, 2) if today_tasks > 0 else 0
    }