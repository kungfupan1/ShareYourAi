"""
节点管理路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
import json

from database import get_db
from models import PluginNode, PluginUser, PluginTask
from schemas import (
    NodeRegister, NodeHeartbeat, NodeResponse,
    MessageResponse
)
from routers.auth import get_current_user
from utils import generate_node_id, get_today_str
from redis_client import redis_client

router = APIRouter(prefix="/api/nodes", tags=["节点管理"])


@router.post("/register", response_model=MessageResponse)
async def register_node(
        node_data: NodeRegister,
        user: PluginUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """注册新节点"""
    # 生成节点 ID
    node_id = generate_node_id()

    # 创建节点
    node = PluginNode(
        node_id=node_id,
        user_id=user.id,
        node_name=node_data.node_name,
        supported_models=json.dumps(node_data.supported_models),
        status='idle',
        last_heartbeat=datetime.now(),
        today_date=get_today_str()
    )

    db.add(node)
    db.commit()

    # 更新 Redis
    redis_client.set_node_online(node_id)

    return MessageResponse(
        success=True,
        message="节点注册成功",
        data={"node_id": node_id}
    )


@router.post("/heartbeat", response_model=MessageResponse)
async def node_heartbeat(
        heartbeat: NodeHeartbeat,
        user: PluginUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """节点心跳"""
    node = db.query(PluginNode).filter(
        PluginNode.node_id == heartbeat.node_id,
        PluginNode.user_id == user.id
    ).first()

    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")

    # 更新心跳时间
    node.last_heartbeat = datetime.now()

    # 检查是否新的一天，重置今日统计
    today = get_today_str()
    if node.today_date != today:
        node.today_date = today
        node.today_tasks = 0
        node.today_success = 0

    db.commit()

    # 更新 Redis 在线状态
    redis_client.set_node_online(node.node_id)

    # 如果节点忙碌，返回当前任务信息
    current_task = None
    if node.status == 'busy' and node.current_task_id:
        task = db.query(PluginTask).filter(
            PluginTask.task_id == node.current_task_id
        ).first()
        if task:
            current_task = {
                "task_id": task.task_id,
                "model_id": task.model_id,
                "prompt": task.prompt,
                "params": json.loads(task.params) if task.params else None
            }

    return MessageResponse(
        success=True,
        message="心跳成功",
        data={
            "status": node.status,
            "current_task": current_task
        }
    )


@router.get("/list", response_model=List[NodeResponse])
async def list_nodes(
        user: PluginUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """获取用户的节点列表"""
    nodes = db.query(PluginNode).filter(
        PluginNode.user_id == user.id
    ).order_by(PluginNode.create_time.desc()).all()

    return [NodeResponse.from_orm(node) for node in nodes]


@router.get("/stats")
async def get_node_stats(
        user: PluginUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """获取用户的节点统计"""
    nodes = db.query(PluginNode).filter(
        PluginNode.user_id == user.id
    ).all()

    # 计算今日统计
    today = get_today_str()
    total_today_tasks = sum(n.today_success or 0 for n in nodes)
    total_today_earnings = sum(n.today_earnings or 0 for n in nodes)

    return {
        "total_nodes": len(nodes),
        "online_nodes": len([n for n in nodes if n.status in ['idle', 'busy']]),
        "today_tasks": total_today_tasks,
        "today_earnings": total_today_earnings
    }


@router.get("/my-nodes")
async def get_my_nodes(
        user: PluginUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """获取用户所有节点详情"""
    nodes = db.query(PluginNode).filter(
        PluginNode.user_id == user.id
    ).order_by(PluginNode.create_time.desc()).all()

    return [
        {
            "node_id": n.node_id,
            "node_name": n.node_name,
            "status": n.status,
            "supported_models": json.loads(n.supported_models) if n.supported_models else [],
            "today_tasks": n.today_tasks or 0,
            "today_earnings": n.today_earnings or 0,
            "last_heartbeat": n.last_heartbeat
        }
        for n in nodes
    ]


@router.get("/tasks")
async def get_user_tasks(
        limit: int = 20,
        user: PluginUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """获取用户所有节点的任务历史"""
    # 获取用户的所有节点ID
    nodes = db.query(PluginNode).filter(
        PluginNode.user_id == user.id
    ).all()
    node_ids = [n.node_id for n in nodes]

    if not node_ids:
        return []

    # 查询这些节点的所有任务
    tasks = db.query(PluginTask).filter(
        PluginTask.assigned_node_id.in_(node_ids)
    ).order_by(PluginTask.create_time.desc()).limit(limit).all()

    return [
        {
            "task_id": t.task_id,
            "model_id": t.model_id,
            "status": t.status,
            "prompt": t.prompt[:50] + '...' if t.prompt and len(t.prompt) > 50 else t.prompt,
            "duration": t.duration_seconds,
            "reward": t.node_reward,
            "create_time": t.create_time
        }
        for t in tasks
    ]


@router.get("/{node_id}", response_model=NodeResponse)
async def get_node(
        node_id: str,
        user: PluginUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """获取节点详情"""
    node = db.query(PluginNode).filter(
        PluginNode.node_id == node_id,
        PluginNode.user_id == user.id
    ).first()

    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")

    return NodeResponse.from_orm(node)


@router.delete("/{node_id}", response_model=MessageResponse)
async def delete_node(
        node_id: str,
        user: PluginUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """删除节点"""
    node = db.query(PluginNode).filter(
        PluginNode.node_id == node_id,
        PluginNode.user_id == user.id
    ).first()

    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")

    if node.status == 'busy':
        raise HTTPException(status_code=400, detail="节点正在执行任务，无法删除")

    db.delete(node)
    db.commit()

    # 删除 Redis 记录
    redis_client.delete_ws_session(node_id)
    redis_client.client.delete(f"node_online:{node_id}")

    return MessageResponse(success=True, message="节点已删除")


@router.get("/{node_id}/tasks")
async def get_node_tasks(
        node_id: str,
        limit: int = 10,
        user: PluginUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """获取节点的任务历史"""
    node = db.query(PluginNode).filter(
        PluginNode.node_id == node_id,
        PluginNode.user_id == user.id
    ).first()

    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")

    tasks = db.query(PluginTask).filter(
        PluginTask.assigned_node_id == node_id
    ).order_by(PluginTask.create_time.desc()).limit(limit).all()

    return {
        "node_id": node_id,
        "tasks": [
            {
                "task_id": t.task_id,
                "model_id": t.model_id,
                "status": t.status,
                "duration": t.duration_seconds,
                "reward": t.node_reward,
                "create_time": t.create_time
            }
            for t in tasks
        ]
    }