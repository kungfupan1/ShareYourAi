"""
数据库模型定义
"""
from sqlalchemy import Column, Integer, String, Boolean, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class PluginUser(Base):
    """插件用户表"""
    __tablename__ = "plugin_users"

    id = Column(Integer, primary_key=True, index=True)

    # 登录信息
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    phone = Column(String(20))
    email = Column(String(100), index=True)

    # 实名信息
    real_name = Column(String(50))
    id_card = Column(String(20))
    is_verified = Column(Boolean, default=False)

    # 收款账户
    alipay_account = Column(String(100))
    wechat_account = Column(String(100))
    bank_card = Column(String(30))
    bank_name = Column(String(50))
    bank_branch = Column(String(100))

    # 余额
    balance = Column(Float, default=0.0)              # 总余额
    withdrawable = Column(Float, default=0.0)         # 可提现
    frozen_settled = Column(Float, default=0.0)       # 冻结-已结算
    frozen_auditing = Column(Float, default=0.0)      # 冻结-待审核
    frozen_withdrawing = Column(Float, default=0.0)   # 冻结-提现中
    total_earned = Column(Float, default=0.0)
    total_withdrawn = Column(Float, default=0.0)

    # 风控
    risk_level = Column(String(20), default='normal')  # normal/warning/danger
    is_blacklisted = Column(Boolean, default=False)

    # 状态
    status = Column(String(20), default='active')
    role = Column(String(20), default='node')  # node/admin

    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 冗余字段
    extra_1 = Column(String(255))
    extra_2 = Column(String(255))
    extra_3 = Column(Text)
    extra_4 = Column(Float)
    extra_5 = Column(Integer)

    # 关联
    nodes = relationship("PluginNode", back_populates="user")
    tasks = relationship("PluginTask", back_populates="user")


class PluginNode(Base):
    """插件节点表"""
    __tablename__ = "plugin_nodes"

    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(String(50), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("plugin_users.id"))

    # 基本信息
    node_name = Column(String(100))
    ip_address = Column(String(50))
    user_agent = Column(String(255))

    # 支持的模型
    supported_models = Column(Text)  # JSON: ["grok_video", "sora2_video"]

    # 状态
    status = Column(String(20), default='offline')  # idle/busy/offline
    current_task_id = Column(String(50))
    last_heartbeat = Column(DateTime)

    # 统计
    total_tasks = Column(Integer, default=0)
    success_tasks = Column(Integer, default=0)
    failed_tasks = Column(Integer, default=0)
    total_earnings = Column(Float, default=0.0)
    avg_duration = Column(Float, default=0.0)

    # 评分
    score = Column(Float, default=50.0)
    success_rate_score = Column(Float, default=50.0)
    speed_score = Column(Float, default=50.0)
    stability_score = Column(Float, default=50.0)

    # 今日统计
    today_tasks = Column(Integer, default=0)
    today_success = Column(Integer, default=0)
    today_earnings = Column(Float, default=0.0)
    today_date = Column(String(10))  # YYYY-MM-DD

    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 冗余字段
    extra_1 = Column(String(255))
    extra_2 = Column(String(255))
    extra_3 = Column(Text)
    extra_4 = Column(Float)
    extra_5 = Column(Integer)

    # 关联
    user = relationship("PluginUser", back_populates="nodes")
    tasks = relationship("PluginTask", back_populates="node")


class PluginModel(Base):
    """AI 模型配置表"""
    __tablename__ = "plugin_models"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(String(50), unique=True, nullable=False, index=True)

    # 基本信息
    name = Column(String(100))
    model_type = Column(String(20))  # video/image
    provider = Column(String(50))    # grok/sora/runway

    # 页面配置
    page_url = Column(String(255))
    timeout = Column(Integer, default=300)
    max_retry = Column(Integer, default=3)

    # 价格配置
    node_reward = Column(Float, default=0.07)   # 节点奖励（给节点用户）
    user_price = Column(Float, default=0.10)    # 用户价格（需求方支付）

    # 校验配置
    min_duration = Column(Integer, default=60)
    max_duration = Column(Integer, default=600)
    min_file_size = Column(Integer, default=1048576)    # 1MB
    max_file_size = Column(Integer, default=209715200)  # 200MB
    allowed_formats = Column(Text)  # JSON: ["mp4", "webm"]
    min_status_checks = Column(Integer, default=2)
    allowed_video_domains = Column(Text)  # JSON: ["*.grok.com"]

    # 频率限制
    max_tasks_per_hour = Column(Integer, default=20)
    max_tasks_per_user_hour = Column(Integer, default=100)

    # 状态
    is_active = Column(Boolean, default=True)

    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 冗余字段
    extra_1 = Column(String(255))
    extra_2 = Column(String(255))
    extra_3 = Column(Text)
    extra_4 = Column(Float)
    extra_5 = Column(Integer)


class PluginTask(Base):
    """任务表"""
    __tablename__ = "plugin_tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(50), unique=True, nullable=False, index=True)

    # 用户关联
    user_id = Column(Integer, ForeignKey("plugin_users.id"))

    # 来源
    source_system = Column(String(50), default='hi-tom-ai')
    source_user_id = Column(Integer)
    source_order_id = Column(String(50))
    source_client_id = Column(String(50))  # 来源平台ID（外部API调用时）

    # 模型
    model_id = Column(String(50), ForeignKey("plugin_models.model_id"))

    # 参数
    prompt = Column(Text)
    images = Column(Text)  # JSON
    params = Column(Text)  # JSON

    # 派单
    assigned_node_id = Column(String(50), ForeignKey("plugin_nodes.node_id"))
    assigned_time = Column(DateTime)
    retry_count = Column(Integer, default=0)

    # 结果
    status = Column(String(20), default='pending')  # pending/processing/success/failed/timeout
    result_url = Column(Text)
    error_message = Column(Text)

    # 校验结果
    validation_status = Column(String(20))  # pending/passed/failed
    validation_result = Column(Text)  # JSON: 详细校验结果
    file_size = Column(Integer)
    file_format = Column(String(20))

    # 链路证据
    proof_data = Column(Text)  # JSON: 请求时间戳、ai_task_id、status_checks等

    # 价格（创建时从模型配置复制）
    node_reward = Column(Float)      # 节点奖励
    user_price = Column(Float)       # 用户支付价格
    deduction_id = Column(String(50))

    # 收益状态
    earning_status = Column(String(20), default='pending')  # pending/auditing/settled/withdrawable/cancelled

    # 时间
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    duration_seconds = Column(Integer)
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 冗余字段
    extra_1 = Column(String(255))
    extra_2 = Column(String(255))
    extra_3 = Column(Text)
    extra_4 = Column(Float)
    extra_5 = Column(Integer)

    # 关联
    user = relationship("PluginUser", back_populates="tasks")
    node = relationship("PluginNode", back_populates="tasks")


class PluginWithdrawal(Base):
    """提现记录表"""
    __tablename__ = "plugin_withdrawals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("plugin_users.id"))

    # 提现信息
    amount = Column(Float, nullable=False)
    method = Column(String(20))  # alipay/wechat/bank
    account = Column(String(100))
    real_name = Column(String(50))

    # 状态
    status = Column(String(20), default='pending')  # pending/processing/completed/rejected

    # 处理信息
    transaction_id = Column(String(100))
    handler_id = Column(Integer)
    handle_time = Column(DateTime)
    handle_note = Column(Text)

    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 冗余字段
    extra_1 = Column(String(255))
    extra_2 = Column(String(255))
    extra_3 = Column(Text)
    extra_4 = Column(Float)
    extra_5 = Column(Integer)


class PluginRiskLog(Base):
    """风控记录表"""
    __tablename__ = "plugin_risk_logs"

    id = Column(Integer, primary_key=True, index=True)

    # 关联
    user_id = Column(Integer, ForeignKey("plugin_users.id"))
    node_id = Column(String(50), ForeignKey("plugin_nodes.node_id"))
    task_id = Column(String(50), ForeignKey("plugin_tasks.task_id"))

    # 风控信息
    risk_type = Column(String(50))  # cheat/frequency/anomaly/other
    risk_level = Column(String(20))  # low/medium/high/critical
    description = Column(Text)

    # 详情
    detail = Column(Text)  # JSON

    # 处理
    handled = Column(Boolean, default=False)
    handler_id = Column(Integer)
    handle_time = Column(DateTime)
    handle_note = Column(Text)

    create_time = Column(DateTime, server_default=func.now())

    # 冗余字段
    extra_1 = Column(String(255))
    extra_2 = Column(String(255))
    extra_3 = Column(Text)
    extra_4 = Column(Float)
    extra_5 = Column(Integer)


class PluginStorageBucket(Base):
    """存储桶配置表"""
    __tablename__ = "plugin_storage_buckets"

    id = Column(Integer, primary_key=True, index=True)

    # 基本信息
    name = Column(String(100))
    bucket_name = Column(String(100), unique=True)
    region = Column(String(50))

    # 密钥
    secret_id = Column(String(255))
    secret_key = Column(String(255))

    # 访问配置
    is_private = Column(Boolean, default=True)
    url_expire_seconds = Column(Integer, default=3600)

    # 状态
    status = Column(String(20), default='active')  # active/archived/disabled
    is_default = Column(Boolean, default=False)

    # 清理策略
    auto_clean = Column(Boolean, default=False)
    retention_days = Column(Integer, default=7)
    clean_scope = Column(Text)  # JSON: ["tasks/videos/", "tasks/images/"]

    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 冗余字段
    extra_1 = Column(String(255))
    extra_2 = Column(String(255))
    extra_3 = Column(Text)
    extra_4 = Column(Float)
    extra_5 = Column(Integer)


class PluginSystemConfig(Base):
    """系统配置表"""
    __tablename__ = "plugin_system_config"

    id = Column(Integer, primary_key=True, index=True)
    config_key = Column(String(100), unique=True, nullable=False)
    config_value = Column(Text)
    config_type = Column(String(20))  # string/number/boolean/json
    description = Column(String(255))

    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PlatformClient(Base):
    """平台客户表 - 外部接入的视频生成平台"""
    __tablename__ = "platform_clients"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(String(50), unique=True, nullable=False, index=True)  # 平台ID，如 CLIENT-ABC123
    client_name = Column(String(100), nullable=False)  # 平台名称
    api_key = Column(String(100), unique=True, nullable=False, index=True)  # API密钥

    # 账户信息
    balance = Column(Float, default=0.0)  # 账户余额
    frozen_balance = Column(Float, default=0.0)  # 冻结金额（预扣费）

    # 联系信息
    contact_name = Column(String(50))  # 联系人
    contact_phone = Column(String(20))  # 联系电话
    contact_email = Column(String(100))  # 联系邮箱

    # 状态
    status = Column(String(20), default='active')  # active/suspended/disabled

    # 统计
    total_calls = Column(Integer, default=0)  # 累计调用次数
    total_spent = Column(Float, default=0.0)  # 累计消费金额
    total_recharged = Column(Float, default=0.0)  # 累计充值金额

    # 安全配置
    ip_whitelist = Column(Text)  # IP白名单（JSON数组）

    # 回调配置
    callback_url = Column(String(500))  # 默认回调地址
    callback_retry_count = Column(Integer, default=0)  # 回调重试次数

    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 关联
    transactions = relationship("ClientTransaction", back_populates="client")
    call_logs = relationship("ClientCallLog", back_populates="client")


class ClientTransaction(Base):
    """平台交易记录表"""
    __tablename__ = "client_transactions"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(String(50), unique=True, nullable=False, index=True)  # 交易ID
    client_id = Column(String(50), ForeignKey("platform_clients.client_id"), nullable=False, index=True)

    # 交易信息
    type = Column(String(20), nullable=False)  # recharge/consume/refund/adjust
    amount = Column(Float, nullable=False)  # 金额（正数加，负数减）
    balance_before = Column(Float, nullable=False)  # 变动前余额
    balance_after = Column(Float, nullable=False)  # 变动后余额

    # 关联信息
    related_task_id = Column(String(50))  # 关联任务ID（消费时）

    # 备注
    remark = Column(String(500))
    operator_id = Column(Integer)  # 操作人ID（管理员操作时）

    create_time = Column(DateTime, server_default=func.now())

    # 关联
    client = relationship("PlatformClient", back_populates="transactions")


class ClientCallLog(Base):
    """平台调用日志表"""
    __tablename__ = "client_call_logs"

    id = Column(Integer, primary_key=True, index=True)
    log_id = Column(String(50), unique=True, nullable=False, index=True)  # 日志ID
    client_id = Column(String(50), ForeignKey("platform_clients.client_id"), nullable=False, index=True)

    # 调用信息
    task_id = Column(String(50), index=True)  # 任务ID
    model_id = Column(String(50))  # 模型ID
    action = Column(String(50), nullable=False)  # 操作：submit/query/cancel/info
    status = Column(String(20))  # 调用状态：success/failed
    cost = Column(Float)  # 扣费金额

    # 请求信息
    ip_address = Column(String(50))  # 调用IP
    user_agent = Column(String(500))  # 客户端标识
    request_params = Column(Text)  # 请求参数（脱敏）
    error_message = Column(Text)  # 错误信息
    response_time = Column(Integer)  # 响应时间（毫秒）

    create_time = Column(DateTime, server_default=func.now())

    # 关联
    client = relationship("PlatformClient", back_populates="call_logs")