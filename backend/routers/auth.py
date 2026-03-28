"""
认证路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
import json

from database import get_db
from models import PluginUser, PluginNode
from schemas import (
    UserRegister, UserLogin, UserResponse, UserUpdate,
    EmailCodeRequest, PasswordReset, TokenResponse,
    MessageResponse
)
from utils import (
    hash_password, verify_password, generate_token,
    generate_code, EmailService, get_today_str
)
from redis_client import redis_client

router = APIRouter(prefix="/api/auth", tags=["认证"])
security = HTTPBearer()

# 邮件服务配置（实际项目中应从配置文件读取）
email_service = None


def init_email_service(smtp_server: str, smtp_port: int,
                       smtp_user: str, smtp_password: str):
    """初始化邮件服务"""
    global email_service
    email_service = EmailService(smtp_server, smtp_port, smtp_user, smtp_password)


def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: Session = Depends(get_db)
) -> PluginUser:
    """获取当前用户"""
    token = credentials.credentials

    # 从 Redis 验证 token
    user_id = redis_client.client.get(f"token:{token}")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证"
        )

    user = db.query(PluginUser).filter(PluginUser.id == int(user_id)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在"
        )

    return user


@router.post("/send-code", response_model=MessageResponse)
async def send_verification_code(request: EmailCodeRequest, db: Session = Depends(get_db)):
    """发送邮箱验证码"""
    if not email_service:
        raise HTTPException(status_code=500, detail="邮件服务未配置")

    # 检查邮箱是否已注册
    existing = db.query(PluginUser).filter(PluginUser.email == request.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="该邮箱已被注册")

    # 生成验证码
    code = generate_code(6)

    # 存储到 Redis
    redis_client.set_email_code(request.email, code)

    # 发送邮件
    success = email_service.send_verification_code(request.email, code)
    if not success:
        raise HTTPException(status_code=500, detail="发送验证码失败")

    return MessageResponse(success=True, message="验证码已发送")


@router.post("/register", response_model=TokenResponse)
async def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """用户注册"""
    # 验证验证码
    stored_code = redis_client.get_email_code(user_data.email)
    if not stored_code or stored_code != user_data.code:
        raise HTTPException(status_code=400, detail="验证码错误或已过期")

    # 检查用户名是否已存在
    if db.query(PluginUser).filter(PluginUser.username == user_data.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")

    # 创建用户
    user = PluginUser(
        username=user_data.username,
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        real_name=user_data.real_name,
        id_card=user_data.id_card,
        is_verified=bool(user_data.real_name and user_data.id_card)
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    # 删除验证码
    redis_client.delete_email_code(user_data.email)

    # 生成 token
    token = generate_token()
    redis_client.client.setex(f"token:{token}", 86400 * 7, str(user.id))  # 7天有效

    return TokenResponse(
        access_token=token,
        user=UserResponse.from_orm(user)
    )


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """用户登录"""
    # 查找用户（支持用户名或邮箱登录）
    user = db.query(PluginUser).filter(
        (PluginUser.username == credentials.username) |
        (PluginUser.email == credentials.username)
    ).first()

    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if user.status != 'active':
        raise HTTPException(status_code=403, detail="账户已被禁用")

    # 生成 token
    token = generate_token()
    redis_client.client.setex(f"token:{token}", 86400 * 7, str(user.id))

    return TokenResponse(
        access_token=token,
        user=UserResponse.from_orm(user)
    )


@router.post("/login-with-code", response_model=TokenResponse)
async def login_with_code(email: str, code: str, db: Session = Depends(get_db)):
    """验证码登录"""
    # 验证验证码
    stored_code = redis_client.get_email_code(email)
    if not stored_code or stored_code != code:
        raise HTTPException(status_code=400, detail="验证码错误或已过期")

    # 查找用户
    user = db.query(PluginUser).filter(PluginUser.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 删除验证码
    redis_client.delete_email_code(email)

    # 生成 token
    token = generate_token()
    redis_client.client.setex(f"token:{token}", 86400 * 7, str(user.id))

    return TokenResponse(
        access_token=token,
        user=UserResponse.from_orm(user)
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(data: PasswordReset, db: Session = Depends(get_db)):
    """重置密码"""
    # 验证验证码
    stored_code = redis_client.get_email_code(data.email)
    if not stored_code or stored_code != data.code:
        raise HTTPException(status_code=400, detail="验证码错误或已过期")

    # 查找用户
    user = db.query(PluginUser).filter(PluginUser.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 更新密码
    user.password_hash = hash_password(data.new_password)
    db.commit()

    # 删除验证码
    redis_client.delete_email_code(data.email)

    return MessageResponse(success=True, message="密码重置成功")


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(user: PluginUser = Depends(get_current_user)):
    """获取当前用户信息"""
    return UserResponse.from_orm(user)


@router.put("/me", response_model=UserResponse)
async def update_current_user(
        update_data: UserUpdate,
        user: PluginUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """更新当前用户信息"""
    if update_data.real_name is not None:
        user.real_name = update_data.real_name
    if update_data.id_card is not None:
        user.id_card = update_data.id_card
    if update_data.alipay_account is not None:
        user.alipay_account = update_data.alipay_account
    if update_data.wechat_account is not None:
        user.wechat_account = update_data.wechat_account
    if update_data.bank_card is not None:
        user.bank_card = update_data.bank_card
    if update_data.bank_name is not None:
        user.bank_name = update_data.bank_name
    if update_data.bank_branch is not None:
        user.bank_branch = update_data.bank_branch

    # 如果填写了实名信息，标记为已验证
    if user.real_name and user.id_card:
        user.is_verified = True

    db.commit()
    db.refresh(user)

    return UserResponse.from_orm(user)


@router.post("/logout", response_model=MessageResponse)
async def logout(
        credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """退出登录"""
    token = credentials.credentials
    redis_client.client.delete(f"token:{token}")
    return MessageResponse(success=True, message="已退出登录")