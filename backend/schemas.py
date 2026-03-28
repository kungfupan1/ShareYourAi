"""
Pydantic Schemas
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime


# ============ 用户相关 ============
class UserRegister(BaseModel):
    username: str = Field(..., min_length=4, max_length=20)
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
    password: str = Field(..., min_length=8, max_length=20)
    real_name: Optional[str] = None
    id_card: Optional[str] = None

    @validator('username')
    def username_format(cls, v):
        import re
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('用户名只能包含字母、数字、下划线')
        return v

    @validator('password')
    def password_strength(cls, v):
        import re
        if not re.search(r'[a-zA-Z]', v) or not re.search(r'[0-9]', v):
            raise ValueError('密码必须包含字母和数字')
        return v


class UserLogin(BaseModel):
    username: str
    password: str


class EmailCodeRequest(BaseModel):
    email: EmailStr


class EmailCodeVerify(BaseModel):
    email: EmailStr
    code: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str]
    role: str = 'node'
    is_verified: bool
    balance: float
    withdrawable: float
    frozen_settled: float
    frozen_auditing: float
    frozen_withdrawing: float
    total_earned: float
    total_withdrawn: float
    risk_level: str
    status: str
    create_time: datetime

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    real_name: Optional[str] = None
    id_card: Optional[str] = None
    alipay_account: Optional[str] = None
    wechat_account: Optional[str] = None
    bank_card: Optional[str] = None
    bank_name: Optional[str] = None
    bank_branch: Optional[str] = None


class PasswordReset(BaseModel):
    email: EmailStr
    code: str
    new_password: str = Field(..., min_length=8, max_length=20)


# ============ 节点相关 ============
class NodeRegister(BaseModel):
    node_name: Optional[str] = None
    supported_models: List[str]


class NodeHeartbeat(BaseModel):
    node_id: str


class NodeResponse(BaseModel):
    id: int
    node_id: str
    node_name: Optional[str]
    status: str
    current_task_id: Optional[str]
    supported_models: Optional[str]
    score: float
    total_tasks: int
    success_tasks: int
    failed_tasks: int
    today_tasks: int
    today_success: int
    last_heartbeat: Optional[datetime]

    class Config:
        from_attributes = True


# ============ 任务相关 ============
class TaskSubmit(BaseModel):
    model_id: str
    prompt: Optional[str] = None
    images: Optional[List[str]] = None
    params: Optional[dict] = None
    source_system: Optional[str] = 'hi-tom-ai'
    source_user_id: Optional[int] = None
    source_order_id: Optional[str] = None


class TaskResult(BaseModel):
    task_id: str
    node_id: str
    status: str  # success/failed
    result_url: Optional[str] = None
    error_message: Optional[str] = None
    proof: Optional[dict] = None
    file_size: Optional[int] = None
    file_format: Optional[str] = None


class TaskResponse(BaseModel):
    id: int
    task_id: str
    model_id: str
    status: str
    assigned_node_id: Optional[str]
    result_url: Optional[str]
    error_message: Optional[str]
    node_reward: Optional[float]
    earning_status: Optional[str]
    duration_seconds: Optional[int]
    create_time: datetime

    class Config:
        from_attributes = True


# ============ 模型相关 ============
class ModelCreate(BaseModel):
    model_id: str
    name: str
    model_type: str
    provider: str
    page_url: Optional[str] = None
    timeout: int = 300
    max_retry: int = 3
    node_reward: float = 0.07   # 节点奖励
    user_price: float = 0.10    # 用户价格
    min_duration: int = 60
    max_duration: int = 600
    min_file_size: int = 1048576
    max_file_size: int = 209715200
    allowed_formats: Optional[List[str]] = None
    min_status_checks: int = 2
    allowed_video_domains: Optional[List[str]] = None
    max_tasks_per_hour: int = 20
    max_tasks_per_user_hour: int = 100


class ModelUpdate(BaseModel):
    name: Optional[str] = None
    page_url: Optional[str] = None
    timeout: Optional[int] = None
    max_retry: Optional[int] = None
    node_reward: Optional[float] = None
    user_price: Optional[float] = None
    min_duration: Optional[int] = None
    max_duration: Optional[int] = None
    min_file_size: Optional[int] = None
    max_file_size: Optional[int] = None
    allowed_formats: Optional[List[str]] = None
    min_status_checks: Optional[int] = None
    allowed_video_domains: Optional[List[str]] = None
    max_tasks_per_hour: Optional[int] = None
    max_tasks_per_user_hour: Optional[int] = None
    is_active: Optional[bool] = None


class ModelResponse(BaseModel):
    id: int
    model_id: str
    name: str
    model_type: str
    provider: str
    node_reward: float
    user_price: float
    is_active: bool

    class Config:
        from_attributes = True


# ============ 提现相关 ============
class WithdrawalRequest(BaseModel):
    amount: float
    method: str  # alipay/wechat/bank
    account: str
    real_name: str

    @validator('amount')
    def amount_positive(cls, v):
        if v <= 0:
            raise ValueError('提现金额必须大于0')
        return v


class WithdrawalResponse(BaseModel):
    id: int
    amount: float
    method: str
    account: str
    status: str
    create_time: datetime

    class Config:
        from_attributes = True


# ============ 系统配置相关 ============
class SystemConfigUpdate(BaseModel):
    config_key: str
    config_value: str


class DispatcherStrategyConfig(BaseModel):
    strategy_type: str  # random/best_node
    success_rate_weight: float = 0.5
    speed_weight: float = 0.3
    stability_weight: float = 0.2
    base_score: float = 50.0
    min_tasks_for_score: int = 10
    consecutive_fail_penalty: float = 0.5
    recent_tasks_count: int = 10


# ============ 通用响应 ============
class MessageResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse