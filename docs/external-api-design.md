# ShareYourAi 外部 API 开放设计文档

> 版本：v1.0
> 日期：2026-03-29
> 状态：设计评审中

---

## 一、背景与目标

### 1.1 背景

ShareYourAi 目前处于自娱自乐阶段，已实现：
- 插件用户通过浏览器插件执行视频生成任务
- 管理后台进行用户、节点、任务管理
- 完整的任务派发、执行、结算流程

### 1.2 目标

将后端 API 开放给外部【视频生成平台】，使其能够：
- 调用我们的 API 申请 Grok 视频生成
- 在管理后台查看和管理接入的平台
- 查看平台调用数据和充值金额
- 支持手动调整平台余额和充值

---

## 二、整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        ShareYourAi 平台                          │
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │  管理后台    │    │  后端 API   │    │  节点系统    │        │
│  │  (Vue)      │    │  (FastAPI)  │    │  (插件)     │        │
│  └─────────────┘    └─────────────┘    └─────────────┘        │
│         │                 │                   │                │
│         │                 │                   │                │
│         ▼                 ▼                   ▼                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                     数据库 + Redis                       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
         ▲
         │ API Key 认证
         │
┌────────┴────────┐  ┌─────────────────┐  ┌─────────────────┐
│  外部平台 A      │  │  外部平台 B      │  │  外部平台 C      │
│  (视频生成网站)   │  │  (APP应用)      │  │  (其他系统)     │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

---

## 三、核心概念

| 概念 | 说明 |
|-----|------|
| **平台客户 (PlatformClient)** | 外部接入的视频生成平台，通过 API 调用我们的服务 |
| **API Key** | 平台客户的身份凭证，用于 API 认证 |
| **平台余额** | 平台客户的预充值金额，调用时扣费 |
| **调用日志** | 每次调用的详细记录 |
| **交易记录** | 余额变动记录（充值、消费、调整） |

### 用户角色对比

| 角色 | 说明 | 收益/支出 |
|-----|------|----------|
| PluginUser（插件用户） | 执行任务，提供算力 | 获得收益（node_reward） |
| AdminUser（管理员） | 管理后台操作 | - |
| PlatformClient（平台客户） | 调用 API 提交任务 | 支付费用（user_price） |

### 资金流向

```
平台客户付费（user_price）
        │
        ▼
    平台余额扣除
        │
        ├──▶ 插件用户获得收益（node_reward）
        │
        └──▶ 平台收益（user_price - node_reward）
```

---

## 四、数据库设计

### 4.1 新增表

#### 4.1.1 平台客户表 `plugin_platform_clients`

```sql
CREATE TABLE plugin_platform_clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id VARCHAR(50) UNIQUE NOT NULL,        -- 平台ID，如 CLIENT-ABC123
    client_name VARCHAR(100) NOT NULL,            -- 平台名称
    api_key VARCHAR(100) UNIQUE NOT NULL,         -- API密钥
    balance DECIMAL(10,2) DEFAULT 0,              -- 账户余额
    frozen_balance DECIMAL(10,2) DEFAULT 0,       -- 冻结金额（预扣费）
    contact_name VARCHAR(50),                     -- 联系人
    contact_phone VARCHAR(20),                    -- 联系电话
    contact_email VARCHAR(100),                   -- 联系邮箱
    status VARCHAR(20) DEFAULT 'active',          -- 状态：active/suspended/disabled
    total_calls INTEGER DEFAULT 0,                -- 累计调用次数
    total_spent DECIMAL(10,2) DEFAULT 0,          -- 累计消费金额
    total_recharged DECIMAL(10,2) DEFAULT 0,      -- 累计充值金额
    ip_whitelist TEXT,                            -- IP白名单（JSON数组，可选）
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### 4.1.2 平台交易记录表 `plugin_client_transactions`

```sql
CREATE TABLE plugin_client_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id VARCHAR(50) UNIQUE NOT NULL,   -- 交易ID
    client_id VARCHAR(50) NOT NULL,               -- 平台ID
    type VARCHAR(20) NOT NULL,                    -- 类型：recharge/consume/refund/adjust
    amount DECIMAL(10,2) NOT NULL,                -- 金额（正数加，负数减）
    balance_before DECIMAL(10,2) NOT NULL,        -- 变动前余额
    balance_after DECIMAL(10,2) NOT NULL,         -- 变动后余额
    related_task_id VARCHAR(50),                  -- 关联任务ID（消费时）
    remark VARCHAR(500),                          -- 备注
    operator_id INTEGER,                          -- 操作人ID（管理员操作时）
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (client_id) REFERENCES plugin_platform_clients(client_id)
);
```

#### 4.1.3 平台调用日志表 `plugin_client_call_logs`

```sql
CREATE TABLE plugin_client_call_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    log_id VARCHAR(50) UNIQUE NOT NULL,           -- 日志ID
    client_id VARCHAR(50) NOT NULL,               -- 平台ID
    task_id VARCHAR(50),                          -- 任务ID
    model_id VARCHAR(50),                         -- 模型ID
    action VARCHAR(50) NOT NULL,                  -- 操作：submit/query/info
    status VARCHAR(20),                           -- 调用状态：success/failed
    cost DECIMAL(10,2),                           -- 扣费金额
    ip_address VARCHAR(50),                       -- 调用IP
    user_agent VARCHAR(500),                      -- 客户端标识
    request_params TEXT,                          -- 请求参数（脱敏）
    error_message TEXT,                           -- 错误信息
    response_time INTEGER,                        -- 响应时间（毫秒）
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (client_id) REFERENCES plugin_platform_clients(client_id)
);
```

### 4.2 修改现有表

#### 4.2.1 任务表 `plugin_tasks` 新增字段

```sql
ALTER TABLE plugin_tasks ADD COLUMN source_client_id VARCHAR(50);  -- 来源平台ID
```

---

## 五、API 认证流程

### 5.1 认证方式

采用 API Key 认证，通过 HTTP Header 传递：

```
X-API-Key: sk_xxxxxxxxxxxxxxxxxxxx
```

### 5.2 认证流程图

```
外部平台发起请求
        │
        ▼
┌─────────────────────┐
│ Header:             │
│ X-API-Key: xxx      │
└─────────────────────┘
        │
        ▼
    查询 API Key 是否存在
        │
        ├─── 不存在 ────────▶ 401 Unauthorized
        │                   {"error": "Invalid API Key"}
        │
        ├─── status=disabled ──▶ 403 Forbidden
        │                      {"error": "Account disabled"}
        │
        ├─── status=suspended ──▶ 403 Forbidden
        │                        {"error": "Account suspended"}
        │
        ▼
    检查 IP 白名单（如已配置）
        │
        ├─── IP 不在白名单 ──▶ 403 Forbidden
        │                     {"error": "IP not allowed"}
        │
        ▼
    检查平台余额
        │
        ├─── 余额不足 ────────▶ 402 Payment Required
        │                      {"error": "Insufficient balance"}
        │
        ▼
    处理请求...
```

### 5.3 API Key 格式

```
sk_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

格式说明：
- 前缀：sk_ (secret key)
- 长度：32位随机字符串
- 示例：sk_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
```

---

## 六、对外 API 接口

### 6.1 基础信息

| 项目 | 说明 |
|-----|------|
| Base URL | `https://shareyouai.winepipeline.com/api/v1` |
| 认证方式 | Header: `X-API-Key: {api_key}` |
| 内容格式 | `Content-Type: application/json` |
| 字符编码 | UTF-8 |

### 6.2 接口列表

| 接口 | 方法 | 说明 |
|-----|------|------|
| `/tasks/submit` | POST | 提交任务 |
| `/tasks/{task_id}` | GET | 查询任务状态 |
| `/tasks/{task_id}/cancel` | POST | 取消任务 |
| `/account/info` | GET | 查询账户信息 |
| `/models` | GET | 获取可用模型列表 |

### 6.3 接口详情

#### 6.3.1 提交任务

**请求**
```
POST /api/v1/tasks/submit
X-API-Key: sk_xxxxxxxxxxxxxxxxxxxx

{
  "model_id": "grok_video",
  "prompt": "一只可爱的猫咪在阳光下跳舞",
  "images": [
    "data:image/png;base64,iVBORw0KGgo..."
  ],
  "params": {
    "duration": 6,
    "aspect_ratio": "16:9",
    "resolution": "1080p"
  },
  "callback_url": "https://your-platform.com/callback",
  "external_id": "YOUR_TASK_12345"
}
```

**参数说明**

| 参数 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| model_id | string | 是 | 模型ID，如 grok_video, sora2_video |
| prompt | string | 是 | 提示词 |
| images | array | 否 | 参考图片（base64），最多5张 |
| params | object | 否 | 生成参数 |
| params.duration | int | 否 | 视频时长（秒） |
| params.aspect_ratio | string | 否 | 画面比例：1:1, 16:9, 9:16 等 |
| params.resolution | string | 否 | 分辨率：480p, 720p, 1080p |
| callback_url | string | 否 | 任务完成回调地址 |
| external_id | string | 否 | 外部平台的任务ID，用于关联 |

**响应**
```json
{
  "success": true,
  "task_id": "T123456789012",
  "estimated_time": 120,
  "cost": 0.10
}
```

**错误响应**
```json
{
  "success": false,
  "error": "Insufficient balance",
  "error_code": "INSUFFICIENT_BALANCE"
}
```

#### 6.3.2 查询任务状态

**请求**
```
GET /api/v1/tasks/T123456789012
X-API-Key: sk_xxxxxxxxxxxxxxxxxxxx
```

**响应**
```json
{
  "success": true,
  "task": {
    "task_id": "T123456789012",
    "status": "success",
    "model_id": "grok_video",
    "prompt": "一只可爱的猫咪在阳光下跳舞",
    "result_url": "https://xxx.cos.ap-guangzhou.myqcloud.com/videos/T123456789012.mp4",
    "duration": 6,
    "file_size": 25600000,
    "created_at": "2026-03-29T10:00:00Z",
    "completed_at": "2026-03-29T10:02:00Z"
  }
}
```

**任务状态说明**

| 状态 | 说明 |
|-----|------|
| pending | 等待处理 |
| processing | 处理中 |
| success | 成功 |
| failed | 失败 |
| timeout | 超时 |
| cancelled | 已取消 |

#### 6.3.3 取消任务

**请求**
```
POST /api/v1/tasks/T123456789012/cancel
X-API-Key: sk_xxxxxxxxxxxxxxxxxxxx
```

**响应**
```json
{
  "success": true,
  "message": "Task cancelled",
  "refund": 0.10
}
```

#### 6.3.4 查询账户信息

**请求**
```
GET /api/v1/account/info
X-API-Key: sk_xxxxxxxxxxxxxxxxxxxx
```

**响应**
```json
{
  "success": true,
  "account": {
    "client_id": "CLIENT-ABC123",
    "client_name": "某视频平台",
    "balance": 1000.00,
    "frozen_balance": 5.00,
    "total_calls": 500,
    "total_spent": 500.00
  }
}
```

#### 6.3.5 获取可用模型列表

**请求**
```
GET /api/v1/models
X-API-Key: sk_xxxxxxxxxxxxxxxxxxxx
```

**响应**
```json
{
  "success": true,
  "models": [
    {
      "model_id": "grok_video",
      "name": "Grok 视频生成",
      "description": "xAI Grok 视频生成模型",
      "price": 0.10,
      "params": {
        "duration": {"min": 1, "max": 60, "default": 5},
        "aspect_ratio": ["1:1", "16:9", "9:16", "3:2", "2:3"],
        "resolution": ["480p", "720p", "1080p"]
      }
    }
  ]
}
```

---

## 七、计费与扣费逻辑

### 7.1 计费标准

使用现有 `plugin_models` 表中的 `user_price` 作为收费标准。

| 模型 | 收费标准（user_price） | 节点收益（node_reward） |
|-----|----------------------|----------------------|
| grok_video | ¥0.10/次 | ¥0.07/次 |
| sora2_video | ¥0.10/次 | ¥0.07/次 |
| runway_video | ¥0.08/次 | ¥0.08/次 |

### 7.2 扣费流程

```
提交任务
    │
    ▼
预扣费（冻结金额）
    │
    │ balance: 100 → 99.90
    │ frozen_balance: 0 → 0.10
    │
    ▼
任务执行
    │
    ├─── 成功 ──▶ 确认扣费
    │              frozen_balance: 0.10 → 0
    │              total_spent: +0.10
    │
    └─── 失败/取消 ──▶ 退回冻结
                       balance: 99.90 → 100
                       frozen_balance: 0.10 → 0
```

### 7.3 余额不足处理

```
提交任务时检查余额
    │
    ├─── balance < user_price ──▶ 拒绝请求
    │                              返回 402 错误
    │
    └─── balance >= user_price ──▶ 正常处理
```

---

## 八、回调通知

### 8.1 回调触发时机

- 任务成功
- 任务失败
- 任务超时

### 8.2 回调格式

**请求**
```
POST {callback_url}
Content-Type: application/json

{
  "event": "task.completed",
  "timestamp": "2026-03-29T10:02:00Z",
  "data": {
    "task_id": "T123456789012",
    "external_id": "YOUR_TASK_12345",
    "status": "success",
    "result_url": "https://xxx.cos.ap-guangzhou.myqcloud.com/videos/T123456789012.mp4",
    "duration": 6,
    "file_size": 25600000
  }
}
```

### 8.3 回调重试机制

| 重试次数 | 间隔 |
|---------|------|
| 第1次 | 1分钟 |
| 第2次 | 5分钟 |
| 第3次 | 15分钟 |
| 第4次 | 1小时 |
| 第5次 | 3小时 |

超过5次重试失败后，停止重试，记录日志。

---

## 九、管理后台功能

### 9.1 菜单结构

```
管理后台
├── 仪表盘
├── 用户管理
├── 节点管理
├── 模型管理
├── 任务管理
├── 收益审核
├── 提现管理
├── 策略配置
├── 风控管理
├── 系统配置
├── 存储配置
├── 【新增】平台客户管理
│   ├── 平台列表
│   ├── 平台详情
│   ├── 交易记录
│   └── 调用日志
└── 测试生成器
```

### 9.2 平台客户列表页

**功能**
- 显示所有平台客户
- 搜索、筛选
- 新增、编辑、停用

**列表字段**

| 字段 | 说明 |
|-----|------|
| 平台名称 | 客户名称 |
| Client ID | 唯一标识 |
| API Key | 脱敏显示（sk_***...***） |
| 余额 | 当前余额 |
| 冻结金额 | 预扣费金额 |
| 状态 | active/suspended/disabled |
| 累计调用 | 调用次数 |
| 累计消费 | 消费金额 |
| 创建时间 | 注册时间 |
| 操作 | 详情、充值、停用、重置Key |

### 9.3 平台详情页

**基本信息卡片**
- 平台名称、Client ID
- API Key（可复制、可重置）
- 联系人、联系电话、联系邮箱
- 状态
- IP白名单

**账户信息卡片**
- 当前余额
- 冻结金额
- 累计充值
- 累计消费

**统计信息卡片**
- 今日调用次数
- 本周调用次数
- 本月调用次数
- 成功率

**操作按钮**
- 充值
- 调整余额
- 启用/停用
- 重置 API Key

### 9.4 充值页面

**表单字段**

| 字段 | 类型 | 说明 |
|-----|------|------|
| 充值金额 | 数字 | 必填，大于0 |
| 支付方式 | 选择 | 线下转账/在线支付（暂只支持线下） |
| 备注 | 文本 | 选填 |

**操作记录**
- 自动创建交易记录
- 记录操作人

### 9.5 余额调整页面

**表单字段**

| 字段 | 类型 | 说明 |
|-----|------|------|
| 调整类型 | 选择 | 增加/减少 |
| 调整金额 | 数字 | 必填，大于0 |
| 调整原因 | 文本 | 必填 |

### 9.6 交易记录页

**筛选条件**
- 时间范围
- 交易类型（充值/消费/调整/退款）

**列表字段**

| 字段 | 说明 |
|-----|------|
| 交易ID | 唯一标识 |
| 类型 | recharge/consume/refund/adjust |
| 金额 | 正数或负数 |
| 变动前余额 | |
| 变动后余额 | |
| 关联任务 | 点击跳转 |
| 备注 | |
| 操作人 | 管理员名称 |
| 时间 | |

### 9.7 调用日志页

**筛选条件**
- 时间范围
- 平台客户
- 操作类型
- 状态

**列表字段**

| 字段 | 说明 |
|-----|------|
| 日志ID | |
| 平台 | |
| 操作 | submit/query/cancel |
| 任务ID | 点击跳转 |
| 模型 | |
| 状态 | success/failed |
| 扣费金额 | |
| IP地址 | |
| 响应时间 | 毫秒 |
| 时间 | |

---

## 十、安全考虑

### 10.1 API Key 安全

| 风险 | 措施 |
|-----|------|
| Key 泄露 | 支持重置 Key，脱敏显示 |
| Key 被盗用 | 记录使用 IP，支持 IP 白名单 |
| Key 明文存储 | 数据库中可加密存储 |

### 10.2 调用安全

| 风险 | 措施 |
|-----|------|
| 恶意调用 | 调用频率限制（每分钟最多 60 次） |
| 余额透支 | 预扣费机制，余额不足直接拒绝 |
| 重复提交 | 支持幂等性（通过 external_id） |

### 10.3 数据安全

| 风险 | 措施 |
|-----|------|
| 数据泄露 | 平台只能查看自己的任务和数据 |
| 敏感信息 | 日志中脱敏处理请求参数 |

---

## 十一、开发计划

### 11.1 优先级

| 优先级 | 功能 | 工作量 | 说明 |
|-------|------|-------|------|
| P0 | 数据库表设计 | 0.5天 | 核心数据结构 |
| P0 | API 认证中间件 | 0.5天 | 认证+扣费逻辑 |
| P0 | 对外 API - 任务提交 | 1天 | 核心接口 |
| P0 | 对外 API - 任务查询 | 0.5天 | 核心接口 |
| P0 | 对外 API - 账户信息 | 0.5天 | 核心接口 |
| P1 | 管理后台 - 平台列表 | 1天 | 基础管理 |
| P1 | 管理后台 - 平台详情 | 1天 | 基础管理 |
| P1 | 管理后台 - 充值/调整 | 1天 | 资金管理 |
| P2 | 调用日志 | 1天 | 问题排查 |
| P2 | 交易记录 | 0.5天 | 财务对账 |
| P3 | 回调通知 | 1天 | 任务完成通知 |
| P3 | IP 白名单 | 0.5天 | 安全增强 |
| P3 | 频率限制 | 0.5天 | 安全增强 |

### 11.2 文件结构

**后端新增文件**
```
backend/
├── models.py           # 新增 PlatformClient, ClientTransaction, ClientCallLog
├── schemas.py          # 新增平台相关 Pydantic schema
├── routers/
│   ├── platform.py     # 新增：平台客户管理 API（管理员）
│   └── v1/
│       ├── __init__.py
│       └── external.py # 新增：对外 API（平台客户）
├── middleware/
│   └── api_key.py      # 新增：API Key 认证中间件
└── services/
    └── billing.py      # 新增：计费服务
```

**前端新增文件**
```
admin-web/src/
├── views/
│   ├── PlatformClient.vue      # 平台客户列表
│   ├── PlatformDetail.vue      # 平台详情
│   └── PlatformRecharge.vue    # 充值/调整弹窗
├── api/
│   └── platform.js             # 平台管理 API
└── router/index.js             # 新增路由配置
```

---

## 十二、与现有系统的关系

### 12.1 系统集成

```
                    ┌─────────────────────┐
                    │   ShareYourAi       │
                    │                     │
┌──────────────┐    │  ┌───────────────┐  │
│ 外部平台 A    │────┼─▶│               │  │
│ (API调用)    │    │  │   对外 API    │  │
└──────────────┘    │  │               │  │
                    │  └───────┬───────┘  │
┌──────────────┐    │          │          │
│ 外部平台 B    │────┼──────────┘          │
│ (API调用)    │    │          │          │
└──────────────┘    │          ▼          │
                    │  ┌───────────────┐  │
                    │  │   任务系统    │  │
                    │  │  (现有逻辑)   │  │
                    │  └───────┬───────┘  │
                    │          │          │
                    │          ▼          │
                    │  ┌───────────────┐  │
                    │  │   节点系统    │  │
                    │  │  (插件用户)   │  │
                    │  └───────────────┘  │
                    │                     │
                    └─────────────────────┘
```

### 12.2 数据关系

```
PlatformClient (平台客户)
    │
    │ 1:N
    ▼
PluginTask (任务)
    │
    │ N:1
    ▼
PluginNode (执行节点) ──▶ PluginUser (插件用户)
```

### 12.3 资金流转

```
┌─────────────────────────────────────────────────────────────┐
│                        资金流转                              │
│                                                             │
│  平台客户                    系统平台                 插件用户  │
│                                                             │
│  ┌─────────┐   充值    ┌─────────┐                     │
│  │         │ ────────▶ │         │                     │
│  │ 余额    │           │ 平台收益 │                     │
│  │         │           │         │                     │
│  │         │   消费    │         │   收益    ┌─────────┐│
│  │         │ ────────▶ │         │ ────────▶│         ││
│  │         │           │         │          │ 余额    ││
│  └─────────┘           └─────────┘          └─────────┘│
│                                                             │
│  消费金额 = user_price                                       │
│  收益金额 = node_reward                                      │
│  平台收益 = user_price - node_reward                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 十三、后续扩展

### 13.1 可能的扩展方向

- 在线支付集成（支付宝、微信）
- 多级代理（平台下可挂子账户）
- 套餐包（预付费套餐，价格优惠）
- 详细的调用统计分析
- SDK 封装（Python、Java、Node.js）

### 13.2 版本规划

| 版本 | 功能 |
|-----|------|
| v1.0 | 基础 API 开放、管理后台基础功能 |
| v1.1 | 回调通知、调用日志完善 |
| v1.2 | IP 白名单、频率限制 |
| v2.0 | 在线支付、套餐包 |

---

## 附录：错误码定义

| 错误码 | HTTP状态码 | 说明 |
|-------|-----------|------|
| INVALID_API_KEY | 401 | API Key 无效 |
| ACCOUNT_DISABLED | 403 | 账户已停用 |
| ACCOUNT_SUSPENDED | 403 | 账户已暂停 |
| IP_NOT_ALLOWED | 403 | IP 不在白名单 |
| INSUFFICIENT_BALANCE | 402 | 余额不足 |
| MODEL_NOT_FOUND | 404 | 模型不存在 |
| TASK_NOT_FOUND | 404 | 任务不存在 |
| INVALID_PARAMS | 400 | 参数错误 |
| RATE_LIMIT_EXCEEDED | 429 | 请求频率超限 |
| INTERNAL_ERROR | 500 | 服务器内部错误 |