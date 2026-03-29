"""
ShareYourAi Backend - FastAPI 主入口
"""
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from database import engine, Base
from routers import auth, nodes, tasks, admin
from websocket import websocket_endpoint

# 创建数据库表
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    # 启动时初始化
    print("ShareYourAi Backend 启动中...")

    # 将所有节点状态重置为 offline（服务器重启后没有 WebSocket 连接）
    from database import SessionLocal
    from models import PluginNode

    db = SessionLocal()
    try:
        db.query(PluginNode).update({"status": "offline"})
        db.commit()
        print("所有节点状态已重置为 offline")
    except Exception as e:
        print(f"重置节点状态失败: {e}")
    finally:
        db.close()

    # 初始化 COS 服务
    from models import PluginStorageBucket
    from services.cos_service import init_cos_service

    db = SessionLocal()
    try:
        bucket = db.query(PluginStorageBucket).filter(
            PluginStorageBucket.is_default == True
        ).first()
        if bucket:
            init_cos_service(
                secret_id=bucket.secret_id,
                secret_key=bucket.secret_key,
                bucket=bucket.bucket_name,
                region=bucket.region
            )
            print(f"COS 服务已初始化: {bucket.bucket_name}")
        else:
            print("未配置默认存储桶，将使用本地存储")
    except Exception as e:
        print(f"初始化 COS 服务失败: {e}")
    finally:
        db.close()

    # 初始化邮件服务（如果有配置）
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if smtp_server and smtp_user and smtp_password:
        from routers.auth import init_email_service
        init_email_service(smtp_server, smtp_port, smtp_user, smtp_password)
        print("邮件服务已初始化")

    # 启动任务超时检查定时任务
    import asyncio
    async def check_timeout_tasks():
        """定时检查超时任务"""
        from models import PluginTask
        from engines.dispatcher import Dispatcher
        while True:
            await asyncio.sleep(60)  # 每60秒检查一次
            try:
                db = SessionLocal()
                # 查找 processing 状态超过 5 分钟的任务
                from datetime import datetime, timedelta
                timeout_threshold = datetime.now() - timedelta(minutes=5)

                timeout_tasks = db.query(PluginTask).filter(
                    PluginTask.status == 'processing',
                    PluginTask.start_time < timeout_threshold
                ).all()

                for task in timeout_tasks:
                    print(f"[超时检查] 任务 {task.task_id} 超时，标记为失败")
                    task.status = 'timeout'
                    task.error_message = "任务执行超时"
                    task.end_time = datetime.now()

                    if task.start_time:
                        task.duration_seconds = int((task.end_time - task.start_time).total_seconds())

                    # 释放节点
                    if task.assigned_node_id:
                        dispatcher = Dispatcher(db)
                        dispatcher.release_node(task.assigned_node_id)
                        dispatcher.update_node_score(task.assigned_node_id, success=False, duration=0)

                    db.commit()
                db.close()
            except Exception as e:
                print(f"[超时检查] 检查失败: {e}")
                try:
                    db.close()
                except:
                    pass

    asyncio.create_task(check_timeout_tasks())
    print("任务超时检查已启动（超时时间：5分钟）")

    # 启动自动审核定时任务
    async def auto_audit_tasks():
        """定时自动审核任务（每30分钟检查一次，审核通过超过24小时的任务）"""
        from models import PluginTask, PluginUser
        from datetime import datetime, timedelta
        while True:
            await asyncio.sleep(1800)  # 每30分钟检查一次
            try:
                db = SessionLocal()
                # 查找 auditing 状态超过 24 小时的任务
                audit_threshold = datetime.now() - timedelta(hours=24)

                auditing_tasks = db.query(PluginTask).filter(
                    PluginTask.earning_status == 'auditing',
                    PluginTask.end_time < audit_threshold,
                    PluginTask.status == 'success'
                ).all()

                for task in auditing_tasks:
                    # 自动审核通过
                    task.earning_status = 'settled'

                    # 更新用户余额
                    user = db.query(PluginUser).filter(PluginUser.id == task.user_id).first()
                    if user:
                        user.frozen_auditing = (user.frozen_auditing or 0) - (task.node_reward or 0)
                        user.frozen_settled = (user.frozen_settled or 0) + (task.node_reward or 0)
                        user.withdrawable = (user.withdrawable or 0) + (task.node_reward or 0)
                        user.balance = (user.balance or 0) + (task.node_reward or 0)
                        user.total_earned = (user.total_earned or 0) + (task.node_reward or 0)

                    print(f"[自动审核] 任务 {task.task_id} 自动审核通过，奖励 {task.node_reward}")

                if auditing_tasks:
                    db.commit()
                    print(f"[自动审核] 本次审核通过 {len(auditing_tasks)} 个任务")

                db.close()
            except Exception as e:
                print(f"[自动审核] 检查失败: {e}")
                try:
                    db.close()
                except:
                    pass

    asyncio.create_task(auto_audit_tasks())
    print("自动审核已启动（审核延迟：24小时）")

    yield

    # 关闭时清理
    print("ShareYourAi Backend 关闭中...")


# 创建应用
app = FastAPI(
    title="ShareYourAi",
    description="分布式 AI 内容生成节点调度平台",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router)
app.include_router(nodes.router)
app.include_router(tasks.router)
app.include_router(admin.router)


# WebSocket 端点
@app.websocket("/ws/{token}/{node_id}")
async def websocket_route(websocket: WebSocket, token: str, node_id: str):
    """WebSocket 连接"""
    await websocket_endpoint(websocket, token, node_id)


# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ShareYourAi Backend"}


# 根路由
@app.get("/")
async def root():
    return {
        "message": "Welcome to ShareYourAi API",
        "docs": "/docs",
        "version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)