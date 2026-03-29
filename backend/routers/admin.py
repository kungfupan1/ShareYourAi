"""
管理后台路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import List, Optional
import json

from database import get_db
from models import (
    PluginUser, PluginNode, PluginTask, PluginModel,
    PluginWithdrawal, PluginRiskLog, PluginStorageBucket,
    PluginSystemConfig
)
from schemas import (
    MessageResponse, ModelCreate, ModelUpdate, ModelResponse,
    WithdrawalRequest, DispatcherStrategyConfig
)
from utils import hash_password

router = APIRouter(prefix="/api/admin", tags=["管理后台"])


def get_admin_user(db: Session, user_id: int) -> PluginUser:
    """获取管理员用户"""
    user = db.query(PluginUser).filter(PluginUser.id == user_id).first()
    if not user or user.role != 'admin':
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


@router.get("/dashboard")
async def get_dashboard(
        user_id: int,
        db: Session = Depends(get_db)
):
    """获取仪表盘数据"""
    admin = get_admin_user(db, user_id)

    # 今日数据
    today = datetime.now().strftime("%Y-%m-%d")

    # 在线节点数
    online_nodes = db.query(PluginNode).filter(
        PluginNode.status.in_(['idle', 'busy'])
    ).count()

    # 处理中任务
    processing_tasks = db.query(PluginTask).filter(
        PluginTask.status == 'processing'
    ).count()

    # 今日任务
    today_tasks = db.query(PluginTask).filter(
        func.date(PluginTask.create_time) == today
    ).count()

    # 今日收益
    today_earnings = db.query(func.sum(PluginTask.node_reward)).filter(
        func.date(PluginTask.create_time) == today,
        PluginTask.status == 'success'
    ).scalar() or 0

    # 近7天任务趋势
    trend_data = []
    for i in range(7):
        date = (datetime.now() - timedelta(days=6-i)).strftime("%Y-%m-%d")
        count = db.query(PluginTask).filter(
            func.date(PluginTask.create_time) == date
        ).count()
        success = db.query(PluginTask).filter(
            func.date(PluginTask.create_time) == date,
            PluginTask.status == 'success'
        ).count()
        trend_data.append({
            "date": date,
            "total": count,
            "success": success
        })

    # 节点状态分布
    node_status = db.query(
        PluginNode.status,
        func.count(PluginNode.id)
    ).group_by(PluginNode.status).all()

    status_distribution = {s: c for s, c in node_status}

    # 最近异常
    recent_risks = db.query(PluginRiskLog).filter(
        PluginRiskLog.handled == False
    ).order_by(PluginRiskLog.create_time.desc()).limit(5).all()

    return {
        "online_nodes": online_nodes,
        "processing_tasks": processing_tasks,
        "today_tasks": today_tasks,
        "today_earnings": round(today_earnings, 2),
        "trend_data": trend_data,
        "node_status_distribution": status_distribution,
        "recent_risks": [
            {
                "id": r.id,
                "risk_type": r.risk_type,
                "risk_level": r.risk_level,
                "description": r.description,
                "create_time": r.create_time
            }
            for r in recent_risks
        ]
    }


# ============ 用户管理 ============
@router.get("/users")
async def list_users(
        user_id: int,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        db: Session = Depends(get_db)
):
    """获取用户列表"""
    admin = get_admin_user(db, user_id)

    query = db.query(PluginUser)

    if status:
        query = query.filter(PluginUser.status == status)

    if keyword:
        query = query.filter(
            (PluginUser.username.contains(keyword)) |
            (PluginUser.email.contains(keyword))
        )

    total = query.count()
    users = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "is_verified": u.is_verified,
                "balance": u.balance,
                "withdrawable": u.withdrawable,
                "total_earned": u.total_earned,
                "risk_level": u.risk_level,
                "is_blacklisted": u.is_blacklisted,
                "status": u.status,
                "create_time": u.create_time
            }
            for u in users
        ]
    }


@router.post("/users/{target_id}/blacklist")
async def toggle_blacklist(
        user_id: int,
        target_id: int,
        db: Session = Depends(get_db)
):
    """切换用户黑名单状态"""
    admin = get_admin_user(db, user_id)

    user = db.query(PluginUser).filter(PluginUser.id == target_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.is_blacklisted = not user.is_blacklisted
    db.commit()

    return MessageResponse(
        success=True,
        message=f"已{'加入' if user.is_blacklisted else '移出'}黑名单"
    )


# ============ 节点管理 ============
@router.get("/nodes")
async def list_nodes(
        user_id: int,
        status: Optional[str] = None,
        model: Optional[str] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        db: Session = Depends(get_db)
):
    """获取节点列表"""
    admin = get_admin_user(db, user_id)

    query = db.query(PluginNode)

    if status:
        query = query.filter(PluginNode.status == status)

    if keyword:
        query = query.filter(PluginNode.node_id.contains(keyword))

    total = query.count()
    nodes = query.offset((page - 1) * page_size).limit(page_size).all()

    # 过滤支持的模型
    if model:
        nodes = [n for n in nodes if model in (n.supported_models or '')]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "nodes": [
            {
                "node_id": n.node_id,
                "user_id": n.user_id,
                "node_name": n.node_name,
                "status": n.status,
                "score": n.score,
                "supported_models": n.supported_models,
                "today_tasks": n.today_tasks,
                "total_tasks": n.total_tasks,
                "success_rate": round(n.success_tasks / n.total_tasks * 100, 1) if n.total_tasks > 0 else 0,
                "last_heartbeat": n.last_heartbeat
            }
            for n in nodes
        ]
    }


# ============ 测试接口 ============
@router.post("/nodes/{node_id}/set-status")
async def set_node_status(
        user_id: int,
        node_id: str,
        status: str,
        db: Session = Depends(get_db)
):
    """设置节点状态（测试用）"""
    admin = get_admin_user(db, user_id)

    node = db.query(PluginNode).filter(PluginNode.node_id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")

    node.status = status
    db.commit()

    return {"success": True, "node_id": node_id, "status": status}


# ============ 模型管理 ============
@router.get("/tasks")
async def list_tasks(
        user_id: int,
        status: Optional[str] = None,
        model_id: Optional[str] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        db: Session = Depends(get_db)
):
    """获取任务列表"""
    admin = get_admin_user(db, user_id)

    query = db.query(PluginTask)

    if status:
        query = query.filter(PluginTask.status == status)

    if model_id:
        query = query.filter(PluginTask.model_id == model_id)

    if keyword:
        query = query.filter(PluginTask.task_id.contains(keyword))

    total = query.count()
    tasks = query.order_by(PluginTask.create_time.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "tasks": [
            {
                "task_id": t.task_id,
                "user_id": t.user_id,
                "model_id": t.model_id,
                "prompt": t.prompt,
                "assigned_node_id": t.assigned_node_id,
                "status": t.status,
                "result_url": t.result_url,
                "error_message": t.error_message,
                "node_reward": t.node_reward,
                "duration_seconds": t.duration_seconds,
                "validation_status": t.validation_status,
                "earning_status": t.earning_status,
                "create_time": t.create_time,
                "end_time": t.end_time
            }
            for t in tasks
        ]
    }


@router.get("/tasks/{task_id}")
async def get_task_detail(
        user_id: int,
        task_id: str,
        db: Session = Depends(get_db)
):
    """获取任务详情"""
    admin = get_admin_user(db, user_id)

    task = db.query(PluginTask).filter(PluginTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 获取签名后的视频 URL
    from routers.tasks import get_signed_video_url
    signed_url = None
    if task.status == 'success' and task.result_url:
        signed_url = get_signed_video_url(task.result_url)

    return {
        "task": {
            "task_id": task.task_id,
            "user_id": task.user_id,
            "model_id": task.model_id,
            "prompt": task.prompt,
            "assigned_node_id": task.assigned_node_id,
            "status": task.status,
            "result_url": signed_url,
            "error_message": task.error_message,
            "node_reward": task.node_reward,
            "duration_seconds": task.duration_seconds,
            "validation_status": task.validation_status,
            "earning_status": task.earning_status,
            "proof_data": task.proof_data,
            "file_size": task.file_size,
            "file_format": task.file_format,
            "create_time": task.create_time,
            "end_time": task.end_time
        }
    }


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
        user_id: int,
        task_id: str,
        db: Session = Depends(get_db)
):
    """取消任务"""
    admin = get_admin_user(db, user_id)

    task = db.query(PluginTask).filter(PluginTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status in ['success', 'failed', 'cancelled', 'timeout']:
        raise HTTPException(status_code=400, detail="任务已完成，无法取消")

    # 更新任务状态
    task.status = 'cancelled'
    task.error_message = '用户手动取消'
    task.end_time = datetime.now()

    # 释放节点
    if task.assigned_node_id:
        node = db.query(PluginNode).filter(
            PluginNode.node_id == task.assigned_node_id
        ).first()
        if node:
            node.status = 'idle'

    db.commit()

    return {"success": True, "message": "任务已取消"}


@router.get("/models", response_model=List[ModelResponse])
async def list_models(
        user_id: int,
        db: Session = Depends(get_db)
):
    """获取模型列表"""
    admin = get_admin_user(db, user_id)

    models = db.query(PluginModel).all()
    return [ModelResponse.from_orm(m) for m in models]


@router.post("/models", response_model=MessageResponse)
async def create_model(
        user_id: int,
        model_data: ModelCreate,
        db: Session = Depends(get_db)
):
    """创建模型"""
    admin = get_admin_user(db, user_id)

    existing = db.query(PluginModel).filter(
        PluginModel.model_id == model_data.model_id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="模型 ID 已存在")

    model = PluginModel(
        model_id=model_data.model_id,
        name=model_data.name,
        model_type=model_data.model_type,
        provider=model_data.provider,
        page_url=model_data.page_url,
        timeout=model_data.timeout,
        max_retry=model_data.max_retry,
        node_reward=model_data.node_reward,
        user_price=model_data.user_price,
        min_duration=model_data.min_duration,
        max_duration=model_data.max_duration,
        min_file_size=model_data.min_file_size,
        max_file_size=model_data.max_file_size,
        allowed_formats=json.dumps(model_data.allowed_formats) if model_data.allowed_formats else None,
        min_status_checks=model_data.min_status_checks,
        allowed_video_domains=json.dumps(model_data.allowed_video_domains) if model_data.allowed_video_domains else None,
        max_tasks_per_hour=model_data.max_tasks_per_hour,
        max_tasks_per_user_hour=model_data.max_tasks_per_user_hour
    )

    db.add(model)
    db.commit()

    return MessageResponse(success=True, message="模型创建成功")


@router.put("/models/{model_id}", response_model=MessageResponse)
async def update_model(
        user_id: int,
        model_id: str,
        model_data: ModelUpdate,
        db: Session = Depends(get_db)
):
    """更新模型"""
    admin = get_admin_user(db, user_id)

    model = db.query(PluginModel).filter(
        PluginModel.model_id == model_id
    ).first()

    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    update_dict = model_data.dict(exclude_unset=True)

    for key, value in update_dict.items():
        if key in ['allowed_formats', 'allowed_video_domains'] and value:
            setattr(model, key, json.dumps(value))
        else:
            setattr(model, key, value)

    db.commit()

    return MessageResponse(success=True, message="模型更新成功")


@router.delete("/models/{model_id}", response_model=MessageResponse)
async def delete_model(
        user_id: int,
        model_id: str,
        db: Session = Depends(get_db)
):
    """删除模型"""
    admin = get_admin_user(db, user_id)

    model = db.query(PluginModel).filter(
        PluginModel.model_id == model_id
    ).first()

    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    db.delete(model)
    db.commit()

    return MessageResponse(success=True, message="模型已删除")


# ============ 收益审核 ============
@router.get("/earnings")
async def list_earnings(
        user_id: int,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        db: Session = Depends(get_db)
):
    """获取收益审核列表"""
    admin = get_admin_user(db, user_id)

    query = db.query(PluginTask).filter(
        PluginTask.earning_status.in_(['auditing', 'settled', 'cancelled'])
    )

    if status:
        query = query.filter(PluginTask.earning_status == status)

    total = query.count()
    tasks = query.order_by(PluginTask.update_time.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return {
        "total": total,
        "tasks": [
            {
                "task_id": t.task_id,
                "node_id": t.assigned_node_id,
                "user_id": t.user_id,
                "model_id": t.model_id,
                "node_reward": t.node_reward,
                "validation_status": t.validation_status,
                "earning_status": t.earning_status,
                "duration": t.duration_seconds,
                "create_time": t.create_time
            }
            for t in tasks
        ]
    }


@router.post("/earnings/{task_id}/approve")
async def approve_earning(
        user_id: int,
        task_id: str,
        db: Session = Depends(get_db)
):
    """通过收益审核"""
    admin = get_admin_user(db, user_id)

    task = db.query(PluginTask).filter(PluginTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.earning_status != 'auditing':
        raise HTTPException(status_code=400, detail="任务不在待审核状态")

    task.earning_status = 'settled'

    # 更新用户余额
    user = db.query(PluginUser).filter(PluginUser.id == task.user_id).first()
    if user:
        user.frozen_auditing = (user.frozen_auditing or 0) - (task.node_reward or 0)
        user.frozen_settled = (user.frozen_settled or 0) + (task.node_reward or 0)
        # 结算后直接进入可提现余额
        user.withdrawable = (user.withdrawable or 0) + (task.node_reward or 0)
        user.balance = (user.balance or 0) + (task.node_reward or 0)
        user.total_earned = (user.total_earned or 0) + (task.node_reward or 0)

    db.commit()

    return MessageResponse(success=True, message="审核通过")


@router.post("/earnings/{task_id}/reject")
async def reject_earning(
        user_id: int,
        task_id: str,
        reason: str,
        db: Session = Depends(get_db)
):
    """拒绝收益"""
    admin = get_admin_user(db, user_id)

    task = db.query(PluginTask).filter(PluginTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    task.earning_status = 'cancelled'
    task.error_message = f"审核拒绝: {reason}"

    # 退还冻结余额
    user = db.query(PluginUser).filter(PluginUser.id == task.user_id).first()
    if user:
        user.frozen_auditing = (user.frozen_auditing or 0) - (task.node_reward or 0)

    db.commit()

    return MessageResponse(success=True, message="已拒绝")


# ============ 提现管理 ============
@router.get("/withdrawals")
async def list_withdrawals(
        user_id: int,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        db: Session = Depends(get_db)
):
    """获取提现列表"""
    admin = get_admin_user(db, user_id)

    query = db.query(PluginWithdrawal)

    if status:
        query = query.filter(PluginWithdrawal.status == status)

    total = query.count()
    withdrawals = query.order_by(PluginWithdrawal.create_time.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return {
        "total": total,
        "withdrawals": [
            {
                "id": w.id,
                "user_id": w.user_id,
                "amount": w.amount,
                "method": w.method,
                "account": w.account,
                "real_name": w.real_name,
                "status": w.status,
                "transaction_id": w.transaction_id,
                "create_time": w.create_time
            }
            for w in withdrawals
        ]
    }


@router.post("/withdrawals/{withdrawal_id}/complete")
async def complete_withdrawal(
        user_id: int,
        withdrawal_id: int,
        transaction_id: str,
        db: Session = Depends(get_db)
):
    """完成提现"""
    admin = get_admin_user(db, user_id)

    withdrawal = db.query(PluginWithdrawal).filter(
        PluginWithdrawal.id == withdrawal_id
    ).first()

    if not withdrawal:
        raise HTTPException(status_code=404, detail="提现记录不存在")

    if withdrawal.status != 'pending':
        raise HTTPException(status_code=400, detail="提现已处理")

    withdrawal.status = 'completed'
    withdrawal.transaction_id = transaction_id
    withdrawal.handle_time = datetime.now()
    withdrawal.handler_id = admin.id

    # 更新用户余额
    user = db.query(PluginUser).filter(PluginUser.id == withdrawal.user_id).first()
    if user:
        user.frozen_withdrawing = (user.frozen_withdrawing or 0) - withdrawal.amount
        user.total_withdrawn = (user.total_withdrawn or 0) + withdrawal.amount
        user.balance = user.balance - withdrawal.amount

    db.commit()

    return MessageResponse(success=True, message="提现完成")


@router.post("/withdrawals/{withdrawal_id}/reject")
async def reject_withdrawal(
        user_id: int,
        withdrawal_id: int,
        reason: str,
        db: Session = Depends(get_db)
):
    """拒绝提现"""
    admin = get_admin_user(db, user_id)

    withdrawal = db.query(PluginWithdrawal).filter(
        PluginWithdrawal.id == withdrawal_id
    ).first()

    if not withdrawal:
        raise HTTPException(status_code=404, detail="提现记录不存在")

    withdrawal.status = 'rejected'
    withdrawal.handle_time = datetime.now()
    withdrawal.handler_id = admin.id
    withdrawal.handle_note = reason

    # 退还余额
    user = db.query(PluginUser).filter(PluginUser.id == withdrawal.user_id).first()
    if user:
        user.frozen_withdrawing = (user.frozen_withdrawing or 0) - withdrawal.amount
        user.withdrawable = (user.withdrawable or 0) + withdrawal.amount

    db.commit()

    return MessageResponse(success=True, message="已拒绝")


# ============ 派单策略配置 ============
@router.get("/dispatcher-strategy")
async def get_dispatcher_strategy(
        user_id: int,
        db: Session = Depends(get_db)
):
    """获取派单策略配置"""
    admin = get_admin_user(db, user_id)

    config = db.query(PluginSystemConfig).filter(
        PluginSystemConfig.config_key == 'dispatcher_strategy'
    ).first()

    if config:
        return json.loads(config.config_value)

    return {
        "strategy_type": "best_node",
        "success_rate_weight": 0.5,
        "speed_weight": 0.3,
        "stability_weight": 0.2,
        "base_score": 50.0,
        "min_tasks_for_score": 10,
        "consecutive_fail_penalty": 0.5,
        "recent_tasks_count": 10
    }


@router.post("/dispatcher-strategy")
async def update_dispatcher_strategy(
        user_id: int,
        config: DispatcherStrategyConfig,
        db: Session = Depends(get_db)
):
    """更新派单策略配置"""
    admin = get_admin_user(db, user_id)

    # 验证权重和
    total_weight = config.success_rate_weight + config.speed_weight + config.stability_weight
    if abs(total_weight - 1.0) > 0.001:
        raise HTTPException(status_code=400, detail="权重之和必须等于 1")

    config_record = db.query(PluginSystemConfig).filter(
        PluginSystemConfig.config_key == 'dispatcher_strategy'
    ).first()

    config_value = json.dumps(config.dict())

    if config_record:
        config_record.config_value = config_value
    else:
        config_record = PluginSystemConfig(
            config_key='dispatcher_strategy',
            config_value=config_value,
            config_type='json'
        )
        db.add(config_record)

    db.commit()

    return MessageResponse(success=True, message="策略配置已更新")


# ============ 系统配置 ============
@router.get("/system-config")
async def get_system_config(
        user_id: int,
        db: Session = Depends(get_db)
):
    """获取系统配置"""
    admin = get_admin_user(db, user_id)

    configs = db.query(PluginSystemConfig).all()

    return {
        "configs": [
            {
                "key": c.config_key,
                "value": c.config_value,
                "type": c.config_type,
                "description": c.description
            }
            for c in configs
        ]
    }


@router.post("/system-config")
async def update_system_config(
        user_id: int,
        key: str,
        value: str,
        db: Session = Depends(get_db)
):
    """更新系统配置"""
    admin = get_admin_user(db, user_id)

    config = db.query(PluginSystemConfig).filter(
        PluginSystemConfig.config_key == key
    ).first()

    if config:
        config.config_value = value
    else:
        config = PluginSystemConfig(config_key=key, config_value=value)
        db.add(config)

    db.commit()

    return MessageResponse(success=True, message="配置已更新")


# ============ 存储桶管理 ============
@router.get("/storage-buckets")
async def list_storage_buckets(
        user_id: int,
        db: Session = Depends(get_db)
):
    """获取存储桶列表"""
    admin = get_admin_user(db, user_id)

    buckets = db.query(PluginStorageBucket).all()

    return {
        "buckets": [
            {
                "id": b.id,
                "name": b.name,
                "bucket_name": b.bucket_name,
                "region": b.region,
                "secret_id": b.secret_id,
                "secret_key": b.secret_key,
                "is_private": b.is_private,
                "is_default": b.is_default,
                "status": b.status,
                "auto_clean": b.auto_clean,
                "retention_days": b.retention_days,
                "create_time": b.create_time
            }
            for b in buckets
        ]
    }


@router.post("/storage-buckets", response_model=MessageResponse)
async def create_storage_bucket(
        user_id: int,
        name: str,
        bucket_name: str,
        region: str,
        secret_id: str,
        secret_key: str,
        is_private: bool = True,
        is_default: bool = False,
        auto_clean: bool = False,
        retention_days: int = 7,
        db: Session = Depends(get_db)
):
    """创建存储桶配置"""
    admin = get_admin_user(db, user_id)

    # 检查 bucket_name 是否已存在
    existing = db.query(PluginStorageBucket).filter(
        PluginStorageBucket.bucket_name == bucket_name
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="存储桶名称已存在")

    # 如果设为默认，取消其他默认
    if is_default:
        db.query(PluginStorageBucket).update({"is_default": False})

    bucket = PluginStorageBucket(
        name=name,
        bucket_name=bucket_name,
        region=region,
        secret_id=secret_id,
        secret_key=secret_key,
        is_private=is_private,
        is_default=is_default,
        auto_clean=auto_clean,
        retention_days=retention_days,
        status='active'
    )

    db.add(bucket)
    db.commit()

    return MessageResponse(success=True, message="存储桶配置创建成功")


@router.put("/storage-buckets/{bucket_id}", response_model=MessageResponse)
async def update_storage_bucket(
        user_id: int,
        bucket_id: int,
        name: str = None,
        secret_id: str = None,
        secret_key: str = None,
        is_private: bool = None,
        is_default: bool = None,
        auto_clean: bool = None,
        retention_days: int = None,
        status: str = None,
        db: Session = Depends(get_db)
):
    """更新存储桶配置"""
    admin = get_admin_user(db, user_id)

    bucket = db.query(PluginStorageBucket).filter(
        PluginStorageBucket.id == bucket_id
    ).first()

    if not bucket:
        raise HTTPException(status_code=404, detail="存储桶不存在")

    if name is not None:
        bucket.name = name
    if secret_id is not None:
        bucket.secret_id = secret_id
    if secret_key is not None:
        bucket.secret_key = secret_key
    if is_private is not None:
        bucket.is_private = is_private
    if is_default is not None:
        if is_default:
            db.query(PluginStorageBucket).update({"is_default": False})
        bucket.is_default = is_default
    if auto_clean is not None:
        bucket.auto_clean = auto_clean
    if retention_days is not None:
        bucket.retention_days = retention_days
    if status is not None:
        bucket.status = status

    db.commit()

    return MessageResponse(success=True, message="存储桶配置更新成功")


@router.delete("/storage-buckets/{bucket_id}", response_model=MessageResponse)
async def delete_storage_bucket(
        user_id: int,
        bucket_id: int,
        db: Session = Depends(get_db)
):
    """删除存储桶配置"""
    admin = get_admin_user(db, user_id)

    bucket = db.query(PluginStorageBucket).filter(
        PluginStorageBucket.id == bucket_id
    ).first()

    if not bucket:
        raise HTTPException(status_code=404, detail="存储桶不存在")

    db.delete(bucket)
    db.commit()

    return MessageResponse(success=True, message="存储桶配置已删除")


@router.post("/storage-buckets/{bucket_id}/test", response_model=MessageResponse)
async def test_storage_bucket(
        user_id: int,
        bucket_id: int,
        db: Session = Depends(get_db)
):
    """测试存储桶连接"""
    admin = get_admin_user(db, user_id)

    bucket = db.query(PluginStorageBucket).filter(
        PluginStorageBucket.id == bucket_id
    ).first()

    if not bucket:
        raise HTTPException(status_code=404, detail="存储桶不存在")

    try:
        from qcloud_cos import CosConfig
        from qcloud_cos import CosS3Client

        config = CosConfig(
            Region=bucket.region,
            SecretId=bucket.secret_id,
            SecretKey=bucket.secret_key
        )
        client = CosS3Client(config)

        # 尝试列出存储桶
        client.list_objects(Bucket=bucket.bucket_name, MaxKeys=1)

        return MessageResponse(success=True, message="存储桶连接测试成功")
    except Exception as e:
        return MessageResponse(success=False, message=f"连接失败: {str(e)}")