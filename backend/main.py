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

    # 初始化 COS 服务
    from database import SessionLocal
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