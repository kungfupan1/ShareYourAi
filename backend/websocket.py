"""
WebSocket 处理
"""
from fastapi import WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from datetime import datetime
import json
import asyncio

from database import SessionLocal, get_db
from models import PluginNode, PluginUser, PluginTask
from redis_client import redis_client
from utils import verify_password


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self.active_connections: dict = {}  # node_id -> WebSocket

    async def connect(self, websocket: WebSocket, node_id: str):
        """接受连接"""
        await websocket.accept()
        self.active_connections[node_id] = websocket
        print(f"节点 {node_id} 已连接")

    def disconnect(self, node_id: str):
        """断开连接"""
        if node_id in self.active_connections:
            del self.active_connections[node_id]
            print(f"节点 {node_id} 已断开")

    async def send_message(self, node_id: str, message: dict):
        """发送消息给指定节点"""
        if node_id in self.active_connections:
            try:
                await self.active_connections[node_id].send_json(message)
            except Exception as e:
                print(f"发送消息失败: {e}")
                self.disconnect(node_id)

    async def broadcast(self, message: dict):
        """广播消息"""
        for node_id in list(self.active_connections.keys()):
            await self.send_message(node_id, message)


manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket, token: str, node_id: str):
    """WebSocket 端点"""
    db = SessionLocal()
    node = None
    heartbeat_task = None

    try:
        # 验证 token
        user_id = redis_client.client.get(f"token:{token}")
        if not user_id:
            await websocket.close(code=4001, reason="认证失败")
            return

        # user_id 可能是 bytes，需要解码
        if isinstance(user_id, bytes):
            user_id = user_id.decode('utf-8')

        # 验证节点归属，如果不存在则自动创建
        node = db.query(PluginNode).filter(
            PluginNode.node_id == node_id,
            PluginNode.user_id == int(user_id)
        ).first()

        if not node:
            # 自动创建节点（基于浏览器指纹）
            node = PluginNode(
                node_id=node_id,
                user_id=int(user_id),
                node_name=f"节点-{node_id[:6]}",
                supported_models='[]',
                status='idle',
                last_heartbeat=datetime.now()
            )
            db.add(node)
            db.commit()
            print(f"自动创建节点: {node_id}")

        # 检查是否已有连接
        existing_session = redis_client.get_ws_session(node_id)
        if existing_session:
            # 踢掉旧连接
            await manager.send_message(node_id, {
                "type": "kicked",
                "reason": "新连接已建立"
            })
            manager.disconnect(node_id)

        # 接受连接
        await manager.connect(websocket, node_id)

        # 记录会话（使用简单的字符串标识）
        redis_client.set_ws_session(node_id, 'active')

        # 更新节点状态
        node.status = 'idle'
        node.last_heartbeat = datetime.now()
        db.commit()

        # 发送连接成功消息
        await manager.send_message(node_id, {
            "type": "connected",
            "node_id": node_id,
            "status": node.status
        })

        # 心跳检测任务
        async def heartbeat_check():
            while True:
                await asyncio.sleep(30)
                try:
                    await manager.send_message(node_id, {"type": "ping"})
                except:
                    break

        # 启动心跳检测
        heartbeat_task = asyncio.create_task(heartbeat_check())

        # 消息循环
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=120  # 2分钟超时
                )

                # 处理消息
                await handle_message(db, node, data)

            except asyncio.TimeoutError:
                await websocket.close(code=4003, reason="心跳超时")
                break
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"处理消息错误: {e}")
                break

    finally:
        # 清理
        if heartbeat_task:
            heartbeat_task.cancel()
        manager.disconnect(node_id)
        redis_client.delete_ws_session(node_id)

        # 更新节点状态
        if node:
            node.status = 'offline'
            db.commit()

        db.close()


async def handle_message(db: Session, node: PluginNode, data: dict):
    """处理 WebSocket 消息"""
    msg_type = data.get('type')

    if msg_type == 'pong':
        # 心跳响应
        node.last_heartbeat = datetime.now()
        db.commit()

    elif msg_type == 'status_update':
        # 状态更新
        new_status = data.get('status')
        if new_status in ['idle', 'busy']:
            node.status = new_status
            db.commit()

    elif msg_type == 'task_result':
        # 任务结果
        task_id = data.get('task_id')
        status = data.get('status')

        task = db.query(PluginTask).filter(PluginTask.task_id == task_id).first()
        if task and task.assigned_node_id == node.node_id:
            task.status = status
            task.result_url = data.get('result_url')
            task.error_message = data.get('error_message')

            if data.get('proof'):
                task.proof_data = json.dumps(data.get('proof'), ensure_ascii=False)

            db.commit()

    else:
        print(f"未知消息类型: {msg_type}")


async def push_task_to_node(node_id: str, task: dict):
    """推送任务给节点"""
    await manager.send_message(node_id, {
        "type": "new_task",
        "task": task
    })