"""
API Key 认证中间件
用于外部 API 的身份验证和权限检查
"""
import json
from typing import Optional
from fastapi import Request, HTTPException, Depends
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db
from models import PlatformClient, ClientCallLog
from services.billing import BillingService
from utils import generate_log_id


# API Key Header 定义
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class APIKeyAuth:
    """API Key 认证类"""

    def __init__(self, db: Session):
        self.db = db
        self.billing = BillingService(db)

    def authenticate(self, api_key: str, ip_address: str = None) -> PlatformClient:
        """
        验证 API Key 并返回平台客户

        Raises:
            HTTPException: 认证失败时抛出
        """
        if not api_key:
            raise HTTPException(
                status_code=401,
                detail={"error": "Missing API Key", "error_code": "MISSING_API_KEY"}
            )

        # 查询平台客户
        client = self.billing.get_client_by_api_key(api_key)

        if not client:
            raise HTTPException(
                status_code=401,
                detail={"error": "Invalid API Key", "error_code": "INVALID_API_KEY"}
            )

        # 检查状态
        if client.status == 'disabled':
            raise HTTPException(
                status_code=403,
                detail={"error": "Account disabled", "error_code": "ACCOUNT_DISABLED"}
            )

        if client.status == 'suspended':
            raise HTTPException(
                status_code=403,
                detail={"error": "Account suspended", "error_code": "ACCOUNT_SUSPENDED"}
            )

        # 检查 IP 白名单
        if client.ip_whitelist:
            try:
                whitelist = json.loads(client.ip_whitelist)
                if whitelist and ip_address and ip_address not in whitelist:
                    raise HTTPException(
                        status_code=403,
                        detail={"error": "IP not allowed", "error_code": "IP_NOT_ALLOWED"}
                    )
            except json.JSONDecodeError:
                pass  # 白名单解析失败，跳过检查

        return client

    def check_balance(self, client: PlatformClient, amount: float) -> None:
        """
        检查余额是否充足

        Raises:
            HTTPException: 余额不足时抛出
        """
        if not self.billing.check_balance(client, amount):
            raise HTTPException(
                status_code=402,
                detail={"error": "Insufficient balance", "error_code": "INSUFFICIENT_BALANCE"}
            )

    def log_call(
        self,
        client: PlatformClient,
        action: str,
        task_id: str = None,
        model_id: str = None,
        status: str = 'success',
        cost: float = None,
        ip_address: str = None,
        user_agent: str = None,
        request_params: dict = None,
        error_message: str = None,
        response_time: int = None
    ) -> ClientCallLog:
        """记录调用日志"""
        log = ClientCallLog(
            log_id=generate_log_id(),
            client_id=client.client_id,
            task_id=task_id,
            model_id=model_id,
            action=action,
            status=status,
            cost=cost,
            ip_address=ip_address,
            user_agent=user_agent,
            request_params=json.dumps(request_params, ensure_ascii=False) if request_params else None,
            error_message=error_message,
            response_time=response_time
        )
        self.db.add(log)
        self.db.commit()
        return log


async def get_api_key(request: Request, api_key: str = Depends(api_key_header)) -> str:
    """从 Header 获取 API Key"""
    return api_key


async def get_client_ip(request: Request) -> str:
    """获取客户端 IP"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def get_authenticated_client(
    request: Request,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
) -> PlatformClient:
    """
    认证依赖项
    用于对外 API 的身份验证
    """
    ip_address = await get_client_ip(request)
    auth = APIKeyAuth(db)
    return auth.authenticate(api_key, ip_address)


def mask_api_key(api_key: str) -> str:
    """脱敏显示 API Key"""
    if not api_key or len(api_key) < 10:
        return api_key
    return f"{api_key[:7]}...{api_key[-4:]}"