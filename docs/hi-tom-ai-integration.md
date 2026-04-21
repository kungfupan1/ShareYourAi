# Hi-Tom-AI 对接 ShareYourAi 技术文档

> 版本：v1.0
> 日期：2026-03-30
> 对接模式：轮询模式

---

## 一、对接概述

### 1.1 背景

Hi-Tom-AI 当前使用 T8Star API 进行视频生成，采用轮询模式获取结果。本次对接将 T8Star 替换为 ShareYourAi 外部 API，保持轮询模式不变。

### 1.2 对接架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         Hi-Tom-AI                                │
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │  用户前端    │───▶│  后端 API   │───▶│ ShareYourAi │         │
│  │  (Vue)      │    │  (FastAPI)  │    │  外部 API   │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│         │                 │                   │                 │
│         │                 │                   │                 │
│         ▼                 ▼                   ▼                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                     Hi-Tom-AI 数据库                      │   │
│  │                  (用户积分、任务记录)                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ API Key 认证
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        ShareYourAi                               │
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │  管理后台    │    │  后端 API   │    │  节点系统    │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                     ShareYourAi 数据库                    │   │
│  │           (平台客户、任务、节点、收益结算)                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 对接要点

| 项目 | 说明 |
|-----|------|
| **对接模式** | 轮询模式（与现有 T8Star 模式一致） |
| **认证方式** | API Key Header 认证 |
| **费用来源** | ShareYourAi 平台客户余额（需提前充值） |
| **用户扣费** | Hi-Tom-AI 自己的积分系统（与 ShareYourAi 费率对应） |

---

## 二、ShareYourAi 外部 API 接口契约

### 2.1 基础信息

| 项目 | 值 |
|-----|-----|
| **Base URL** | `https://shareyouai.winepipeline.com/api/v1` |
| **认证方式** | Header: `X-API-Key: {api_key}` |
| **内容格式** | `Content-Type: application/json` |
| **字符编码** | UTF-8 |

### 2.2 API Key 获取

1. 登录 ShareYourAi 管理后台：`https://shareyouai.winepipeline.com`
2. 进入"平台客户"页面，创建新平台客户
3. 填写平台信息：
   - 平台名称：`Hi-Tom-AI`
   - 联系人/联系方式（可选）
4. 创建成功后，系统返回：
   - `client_id`: 平台唯一标识
   - `api_key`: API 密钥（格式 `sk_xxxxx...`）
5. 为平台充值余额（可通过管理后台充值）

### 2.3 接口列表

| 接口 | 方法 | 说明 | 用途 |
|-----|------|------|------|
| `/tasks/submit` | POST | 提交任务 | 替代 T8Star 视频生成接口 |
| `/tasks/{task_id}` | GET | 查询任务状态 | 替代 T8Star 状态查询接口 |
| `/tasks/{task_id}/cancel` | POST | 取消任务 | 用户取消/超时退款 |
| `/account/info` | GET | 查询账户余额 | 监控平台余额 |
| `/models` | GET | 获取可用模型列表 | 动态获取模型配置 |

---

## 三、核心接口详细说明

### 3.1 提交任务

**接口**：`POST /api/v1/tasks/submit`

**请求头**：
```
X-API-Key: sk_your_api_key_here
Content-Type: application/json
```

**请求体**：
```json
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
  "callback_url": "https://hi-tom-ai.com/api/callback",
  "external_id": "HITOM_12345"
}
```

**请求参数说明**：

| 参数 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| `model_id` | string | **是** | 模型ID，见下表 |
| `prompt` | string | **是** | 视频生成提示词 |
| `images` | array | 否 | 参考图片（base64编码），最多5张 |
| `params` | object | 否 | 生成参数 |
| `params.duration` | int | 否 | 视频时长（秒），建议 5-60 |
| `params.aspect_ratio` | string | 否 | 画面比例：`1:1`、`16:9`、`9:16` |
| `params.resolution` | string | 否 | 分辨率：`480p`、`720p`、`1080p` |
| `callback_url` | string | 否 | 回调地址（暂未实现，可忽略） |
| `external_id` | string | 否 | Hi-Tom-AI 自己的任务ID，用于关联 |

**可用模型**：

| model_id | 说明 | 收费(元/次) | 建议对应 |
|----------|------|------------|---------|
| `grok_video` | Grok 视频生成 | ¥0.30 | Hi-Tom-AI 的 "Grok Video 3" |
| `sora2_video` | Sora2 视频生成 | ¥0.10 | Hi-Tom-AI 的 "Sora-2" |
| `runway_video` | Runway 视频生成 | ¥0.12 | 可扩展 |

**成功响应**：
```json
{
  "success": true,
  "task_id": "T123456789012",
  "estimated_time": 300,
  "cost": 0.30
}
```

**响应字段说明**：

| 字段 | 类型 | 说明 |
|-----|------|------|
| `success` | boolean | 是否成功 |
| `task_id` | string | ShareYourAi 任务ID，用于后续查询 |
| `estimated_time` | int | 预估完成时间（秒） |
| `cost` | decimal | 本次扣费金额（元） |

**失败响应**：

| error_code | HTTP状态码 | 说明 | 处理建议 |
|------------|-----------|------|---------|
| `INVALID_API_KEY` | 401 | API Key 无效 | 检查 API Key 配置 |
| `ACCOUNT_DISABLED` | 403 | 账户已停用 | 联系 ShareYourAi 管理员 |
| `INSUFFICIENT_BALANCE` | 402 | 余额不足 | 提醒充值 |
| `MODEL_NOT_FOUND` | 404 | 模型不存在 | 检查 model_id |
| `NO_AVAILABLE_NODES` | 200 | 无可用节点 | 稍后重试或降级到 T8Star |

**错误响应示例**：
```json
{
  "success": false,
  "error": "Insufficient balance",
  "error_code": "INSUFFICIENT_BALANCE"
}
```

---

### 3.2 查询任务状态

**接口**：`GET /api/v1/tasks/{task_id}`

**请求头**：
```
X-API-Key: sk_your_api_key_here
```

**请求示例**：
```
GET https://shareyouai.winepipeline.com/api/v1/tasks/T123456789012
```

**成功响应**：
```json
{
  "success": true,
  "task": {
    "task_id": "T123456789012",
    "status": "success",
    "model_id": "grok_video",
    "prompt": "一只可爱的猫咪在阳光下跳舞",
    "result_url": "https://shareyouai-xxx.cos.ap-guangzhou.myqcloud.com/videos/2026/03/T123456789012.mp4?sign=xxx",
    "duration": 6,
    "file_size": 25600000,
    "created_at": "2026-03-30T10:00:00Z",
    "completed_at": "2026-03-30T10:02:00Z"
  }
}
```

**任务状态说明**：

| status | 说明 | Hi-Tom-AI 对应处理 |
|--------|------|------------------|
| `pending` | 等待处理 | 显示"等待中"，继续轮询 |
| `processing` | 处理中 | 显示"生成中"，继续轮询 |
| `success` | 成功完成 | 停止轮询，返回视频URL给用户 |
| `failed` | 失败 | 停止轮询，提示用户重试，退还积分 |
| `timeout` | 超时 | 停止轮询，提示用户重试，退还积分 |
| `cancelled` | 已取消 | 停止轮询，已退款 |

**响应字段说明**：

| 字段 | 类型 | 说明 |
|-----|------|------|
| `task_id` | string | 任务ID |
| `status` | string | 任务状态 |
| `model_id` | string | 使用的模型 |
| `prompt` | string | 提示词 |
| `result_url` | string | 视频下载URL（带签名，有效期1小时） |
| `duration` | int | 视频时长（秒） |
| `file_size` | int | 文件大小（字节） |
| `created_at` | string | 创建时间（ISO8601） |
| `completed_at` | string | 完成时间（ISO8601） |

---

### 3.3 取消任务

**接口**：`POST /api/v1/tasks/{task_id}/cancel`

**请求头**：
```
X-API-Key: sk_your_api_key_here
```

**成功响应**：
```json
{
  "success": true,
  "message": "Task cancelled",
  "refund": 0.30
}
```

**说明**：
- 只有 `pending` 状态的任务可以取消并全额退款
- `processing` 状态的任务取消不退款（节点已在执行）
- `success`/`failed`/`timeout` 状态的任务不能取消

---

### 3.4 查询账户余额

**接口**：`GET /api/v1/account/info`

**请求头**：
```
X-API-Key: sk_your_api_key_here
```

**响应**：
```json
{
  "success": true,
  "account": {
    "client_id": "CLIENT-ABC123",
    "client_name": "Hi-Tom-AI",
    "balance": 1000.00,
    "frozen_balance": 5.00,
    "total_calls": 500,
    "total_spent": 150.00
  }
}
```

**用途**：
- 定期监控 ShareYourAi 余额
- 余额低于阈值时告警提醒充值
- 可在后端定时任务中调用

---

### 3.5 获取可用模型列表

**接口**：`GET /api/v1/models`

**请求头**：
```
X-API-Key: sk_your_api_key_here
```

**响应**：
```json
{
  "success": true,
  "models": [
    {
      "model_id": "grok_video",
      "name": "Grok 视频生成",
      "description": "xAI Grok 视频生成模型",
      "price": 0.30,
      "params": {
        "duration": {"min": 1, "max": 60, "default": 5},
        "aspect_ratio": ["1:1", "16:9", "9:16"],
        "resolution": ["480p", "720p", "1080p"]
      }
    },
    {
      "model_id": "sora2_video",
      "name": "Sora2 视频生成",
      "description": "OpenAI Sora2 视频生成模型",
      "price": 0.10,
      "params": {...}
    }
  ]
}
```

---

## 四、Hi-Tom-AI 对接改造指南

### 4.1 需要修改的文件

| 文件 | 改动内容 |
|-----|---------|
| `user-web/src/api/index.js` | 新增 ShareYourAi API 调用方法 |
| `user-web/src/api/request.js` | 新增 ShareYourAi Axios 实例（带 X-API-Key） |
| `user-web/src/views/ai/VideoTool.vue` | 调用逻辑切换（T8Star → ShareYourAi） |
| `backend/main.py` | 新增 ShareYourAi 配置（API Key、Base URL） |
| 环境配置 | 存储 ShareYourAi API Key |

### 4.2 配置项

在 Hi-Tom-AI 后端或前端环境变量中添加：

```env
# ShareYourAi 配置
SHAREYOURAI_API_BASE=https://shareyouai.winepipeline.com/api/v1
SHAREYOURAI_API_KEY=sk_xxxxxxxx  # 从管理后台获取
```

### 4.3 API 调用封装示例

```javascript
// user-web/src/api/shareyourai.js

import axios from 'axios'

const shareYourAiClient = axios.create({
  baseURL: 'https://shareyouai.winepipeline.com/api/v1',
  headers: {
    'X-API-Key': 'sk_xxxxxxxx',  // 从环境变量读取
    'Content-Type': 'application/json'
  }
})

// 提交任务
export function submitVideoTask(data) {
  return shareYourAiClient.post('/tasks/submit', {
    model_id: data.model_id,      // grok_video / sora2_video
    prompt: data.prompt,
    images: data.images,          // base64 数组
    params: {
      duration: data.duration,
      aspect_ratio: data.aspect_ratio,
      resolution: data.resolution
    },
    external_id: data.external_id  // Hi-Tom-AI 任务ID
  })
}

// 查询任务状态
export function getTaskStatus(taskId) {
  return shareYourAiClient.get(`/tasks/${taskId}`)
}

// 取消任务
export function cancelTask(taskId) {
  return shareYourAiClient.post(`/tasks/${taskId}/cancel`)
}

// 查询余额
export function getAccountInfo() {
  return shareYourAiClient.get('/account/info')
}
```

### 4.4 轮询配置调整

ShareYourAi 视频生成时间约为 **2-5 分钟**，建议调整轮询参数：

```javascript
// 原配置（T8Star）
const pollingConfig = {
  interval: 15000,      // 15秒
  maxAttempts: 120,     // 120次 = 30分钟
  timeout: 600000       // 10分钟
}

// 建议配置（ShareYourAi）
const pollingConfig = {
  interval: 30000,      // 30秒（降低请求频率）
  maxAttempts: 20,      // 20次 = 10分钟
  timeout: 600000       // 保持10分钟
}
```

### 4.5 模型映射

Hi-Tom-AI 模型 → ShareYourAi model_id：

| Hi-Tom-AI 前端显示 | ShareYourAi model_id | 收费 | Hi-Tom-AI 积分定价建议 |
|-------------------|----------------------|------|---------------------|
| Grok Video 3 | `grok_video` | ¥0.30 | 30积分 |
| Sora-2 | `sora2_video` | ¥0.10 | 10积分 |
| Sora-2 Pro | `sora2_video` | ¥0.10 | 15积分（加服务费） |

### 4.6 错误处理策略

| 错误场景 | 处理方式 |
|---------|---------|
| ShareYourAi 余额不足 | 提示管理员充值，临时降级到 T8Star |
| 无可用节点 (NO_AVAILABLE_NODES) | 稍后重试（5秒后），或降级到 T8Star |
| 任务超时/失败 | 退还用户积分，记录日志 |
| API Key 无效 | 告警通知，暂停服务 |

---

## 五、费用结算流程

### 5.1 ShareYourAi 扣费机制

```
提交任务 → 预扣费（冻结）
         → 任务成功 → 确认扣费
         → 任务失败/取消 → 退款
```

### 5.2 Hi-Tom-AI 积分扣费流程（保持现有逻辑）

Hi-Tom-AI 自己的积分系统与 ShareYourAi 解耦：

1. 用户在 Hi-Tom-AI 消耗积分
2. Hi-Tom-AI 后端调用 ShareYourAi（ShareYourAi 扣平台余额）
3. ShareYourAi 余额由 Hi-Tom-AI 管理员充值

### 5.3 资金流向

```
用户支付积分 → Hi-Tom-AI 积分系统
                    ↓
ShareYourAi 平台余额 ← 管理员充值
                    ↓
ShareYourAi 扣费 → 节点用户获得收益
```

---

## 六、测试验证清单

### 6.1 对接前准备

- [ ] 在 ShareYourAi 管理后台创建 Hi-Tom-AI 平台客户
- [ ] 获取并保存 API Key
- [ ] 充值测试余额（建议充值 ¥50 进行测试）
- [ ] 确认 ShareYourAi 有在线节点（管理后台"节点管理"页面）

### 6.2 功能测试

- [ ] 提交 Grok 视频任务成功
- [ ] 提交 Sora2 视频任务成功
- [ ] 轮询获取任务状态正常
- [ ] 任务成功后获取视频URL
- [ ] 视频URL可以正常下载
- [ ] 取消任务功能正常
- [ ] 余额查询接口正常
- [ ] 余额不足时正确报错

### 6.3 异常测试

- [ ] API Key 错误时返回 401
- [ ] 余额不足时返回 INSUFFICIENT_BALANCE
- [ ] 无可用节点时返回 NO_AVAILABLE_NODES
- [ ] 任务超时后自动退款
- [ ] 任务失败后自动退款

---

## 七、联系与支持

### 7.1 ShareYourAi 管理后台

- URL: `https://shareyouai.winepipeline.com`
- 管理员账号: `admin`
- 功能: 平台管理、充值、余额查看、节点状态

### 7.2 技术支持

如遇对接问题，可通过以下方式排查：
1. 查看 ShareYourAi API 文档: `/docs` (Swagger UI)
2. 检查 ShareYourAi 管理后台的"调用日志"
3. 检查 ShareYourAi 管理后台的"任务管理"

---

## 附录：完整请求示例

### A.1 提交 Grok 视频任务

```bash
curl -X POST "https://shareyouai.winepipeline.com/api/v1/tasks/submit" \
  -H "X-API-Key: sk_abc123def456" \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "grok_video",
    "prompt": "一只可爱的橘猫在阳光下慵懒地伸懒腰，背景是绿色的草地和蓝天",
    "params": {
      "duration": 6,
      "aspect_ratio": "9:16",
      "resolution": "1080p"
    },
    "external_id": "HITOM_TEST_001"
  }'
```

**预期响应**：
```json
{
  "success": true,
  "task_id": "T996145748986",
  "estimated_time": 300,
  "cost": 0.30
}
```

### A.2 查询任务状态

```bash
curl "https://shareyouai.winepipeline.com/api/v1/tasks/T996145748986" \
  -H "X-API-Key: sk_abc123def456"
```

**轮询直到 status = success**：

```json
{
  "success": true,
  "task": {
    "task_id": "T996145748986",
    "status": "success",
    "result_url": "https://shareyouai-xxx.cos.ap-guangzhou.myqcloud.com/videos/2026/03/T996145748986.mp4?sign=xxx",
    "duration": 6,
    "file_size": 12582912
  }
}
```

### A.3 查询账户余额

```bash
curl "https://shareyouai.winepipeline.com/api/v1/account/info" \
  -H "X-API-Key: sk_abc123def456"
```

**响应**：
```json
{
  "success": true,
  "account": {
    "client_id": "CLIENT-HITOM001",
    "client_name": "Hi-Tom-AI",
    "balance": 49.70,
    "frozen_balance": 0.00,
    "total_calls": 1,
    "total_spent": 0.30
  }
}
```

---

## 附录 B：错误码完整列表

| 错误码 | HTTP状态 | 说明 | Hi-Tom-AI 处理建议 |
|-------|---------|------|------------------|
| `INVALID_API_KEY` | 401 | API Key 无效或不存在 | 检查配置，联系管理员 |
| `ACCOUNT_DISABLED` | 403 | 账户已停用 | 联系 ShareYourAi 管理员 |
| `ACCOUNT_SUSPENDED` | 403 | 账户已暂停 | 联系 ShareYourAi 管理员 |
| `IP_NOT_ALLOWED` | 403 | IP不在白名单 | 联系管理员添加IP白名单 |
| `INSUFFICIENT_BALANCE` | 402 | 余额不足 | 提示充值，降级到备用服务商 |
| `MODEL_NOT_FOUND` | 404 | 模型不存在 | 检查 model_id 参数 |
| `TASK_NOT_FOUND` | 404 | 任务不存在 | 检查 task_id，可能已过期 |
| `NO_AVAILABLE_NODES` | 200 | 无可用节点 | 稍后重试或降级 |
| `INVALID_PARAMS` | 400 | 参数错误 | 检查请求参数格式 |
| `RATE_LIMIT_EXCEEDED` | 429 | 频率超限 | 降低调用频率 |
| `INTERNAL_ERROR` | 500 | 服务器内部错误 | 稍后重试，联系管理员 |