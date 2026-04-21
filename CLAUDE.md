# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ShareYourAi is a distributed AI content generation node scheduling platform. It operates on a "ride-hailing" model:
- **Demand side**: Submits AI generation tasks (video/image) via external systems
- **Node side**: Runs browser plugin to operate AI web pages and complete tasks for rewards
- **Platform side**: Dispatches tasks, settles earnings, manages nodes and users

## Development Commands

### Backend (FastAPI)
```bash
cd backend
pip install -r requirements.txt
python init_db.py           # Initialize database + create admin user
uvicorn main:app --reload --port 8000
```

Default admin credentials: `admin` / `admin123`

### Admin Web (Vue 3)
```bash
cd admin-web
npm install
npm run dev                 # Development server (port 8081)
npm run build               # Production build
npm run preview             # Preview production build locally
```

Dev server (vite.config.js) proxies `/api` → `http://localhost:8000` and `/ws` → `ws://localhost:8000`. API requests use `baseURL: '/api'` via axios (`src/api/request.js`).

### Docker (Production)
```bash
docker-compose up -d        # Start all services (Redis, Backend, Nginx)
docker-compose down         # Stop all services
docker-compose build        # Rebuild backend image after code changes
```
Services: Redis (cache), Backend (port 8000), Nginx (port 8082 for admin-web)

**Note**: Backend startup resets all node statuses to `offline` since no WebSocket connections exist after restart.

### Plugin (Chrome Extension)
Load the `plugin/` directory as an unpacked extension in Chrome. No build step required.

**Environment switching**: Change `ENV` constant in both files:
- `plugin/background/index.js` (line 7)
- `plugin/config.js` (line 7)

Options: `'development'` (localhost:8000) or `'production'` (shareyouai.winepipeline.com)

Note: Production uses HTTPS/WSS, development uses HTTP/WS.

## Architecture

### Backend Structure (`backend/`)
- `main.py` - FastAPI app entry point, CORS config, router registration. Built-in API docs at `/docs`
- `database.py` - SQLAlchemy setup with SQLite (`shareyourai.db` locally, `share_you_ai.db` in Docker)
- `redis_client.py` - Redis client for task queues, node status, sessions
- `models.py` - All SQLAlchemy models (PluginUser, PluginNode, PluginTask, etc.)
- `schemas.py` - Pydantic schemas for request/response validation
- `routers/` - API endpoints:
  - `auth.py` - User registration, login, JWT tokens
  - `nodes.py` - Node registration, heartbeat, status management
  - `tasks.py` - Task submission, results, legacy external API
  - `admin.py` - Admin dashboard, user/node/model management
  - `platform.py` - Platform client management (admin)
  - `v1/external.py` - External API v1 for platform clients
- `middleware/`:
  - `api_key.py` - API Key header authentication for external API
- `websocket.py` - WebSocket connection manager for real-time node communication
- `services/` - External service integrations:
  - `cos_service.py` - Tencent COS cloud storage (file upload, signed URLs)
  - `billing.py` - Platform client billing (balance freeze, deduction, refund)
- `utils/` - Shared utilities (`__init__.py`): ID generators (task, node, client, API key), password hashing (bcrypt), email service, file type detection, time helpers
- `engines/`:
  - `dispatcher.py` - Task dispatch with random or best-node strategies
  - `validator.py` - Task result validation (anti-cheat)

### Frontend Structure (`admin-web/src/`)
- Vue 3 + Vue Router + Pinia + Element Plus + ECharts
- `views/` - Dashboard, UserManage, NodeManage, ModelManage, TaskManage, EarningAudit, WithdrawalManage, StrategyConfig, RiskControl, SystemConfig, StorageConfig, TestGenerator (for simulating task submissions)
- `api/` - HTTP request wrappers for backend API calls
- `stores/auth.js` - Authentication state management
- `router/index.js` - Route definitions with auth guard

### Plugin Structure (`plugin/`)
- Chrome Extension Manifest V3
- `background/index.js` - Service worker handling task routing and API communication
- `content/` - Content scripts for intercepting AI page requests:
  - `bridge.js` - Creates message channel between page script and content script
  - `inject.js` - Injected into page context to intercept fetch/XHR responses (MV3 can't read response bodies in background)
  - `index.js` - Content script that coordinates with injected script and background
- `popup/` - Extension popup UI
- `config.js` - Environment configuration (API_BASE, WS_URL)
- Supported AI platforms: `grok.com`, `sora.com`, `runwayml.com` (configured in manifest.json)

## Key Concepts

### Node States
- `idle` - Available for tasks
- `busy` - Currently processing a task
- `offline` - Disconnected

### Task Flow
1. Task submitted → `pending` status → pushed to Redis queue
2. Dispatcher selects node based on strategy → `processing`
3. Plugin executes on AI page, captures proof data
4. Result submitted → `success`/`failed`/`timeout`
5. Validator checks result integrity
6. If passed → `earning_status: auditing` → admin approval → `settled`

### Pricing Model
- `node_reward` - Reward paid to node users for completing tasks
- `user_price` - Price charged to demand-side users
- Platform margin = `user_price - node_reward` (implicit, not stored)

### Anti-Cheat Layers
1. Plugin-side chain verification (intercepts AI API requests as proof)
2. COS upload credentials bound to task_id (5-min expiry)
3. Backend file validation (size, format, duration)
4. Delayed reward settlement with manual audit

## Database Models

Key tables and their relationships:
- `plugin_users` - Node operators with balance tracking (withdrawable, frozen_settled, frozen_auditing, frozen_withdrawing)
- `plugin_nodes` - Browser instances with scores, supported models, statistics
- `plugin_tasks` - Tasks with proof_data, validation_status, earning_status
- `plugin_models` - AI model configurations (node_reward, user_price, validation rules)
- `plugin_withdrawals` - Withdrawal records
- `plugin_risk_logs` - Risk control records
- `platform_clients` - External platforms consuming the API (balance, frozen_balance, api_key)
- `client_transactions` - Platform transaction records (recharge/consume/refund/adjust)
- `client_call_logs` - Platform API call logs

Default models initialized by `init_db.py`:
- `grok_video` - Grok 视频生成 (node_reward: 0.07)
- `sora2_video` - Sora2 视频生成 (node_reward: 0.07)
- `runway_video` - Runway 视频生成 (node_reward: 0.08)

## Environment Variables

Backend supports these optional environment variables:
- `REDIS_URL` - Redis connection URL (default: `redis://localhost:6379/0`)
- `SMTP_SERVER`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` - Email service for verification codes

## Health Check

Backend endpoint: `/health` - Returns `{"status": "healthy", "service": "ShareYourAi Backend"}`

## Backend Background Tasks

FastAPI lifespan in `main.py` runs two background tasks:
- **Timeout checker**: Every 60 seconds, marks `processing` tasks exceeding 5 minutes as `timeout`
- **Auto-audit**: Every 30 minutes, auto-approves `auditing` tasks that succeeded > 24 hours ago, moving them to `settled` and updating user balances

## Upload Limits

- Nginx: `client_max_body_size 50M` (configured in nginx.conf)
- COS credentials: 5-minute expiry for presigned PUT URLs, bound to task_id

## API Authentication

- User endpoints: Bearer token in Authorization header
- Admin endpoints: `user_id` query parameter (simplified auth for admin panel)
- External API v1: `X-API-Key` header validated against `platform_clients.api_key`

### External API Endpoints

Two versions of external API exist:

**Legacy External API** (deprecated, uses query parameter):
- `POST /api/tasks/external/submit?api_key=xxx` - Submit task
- `GET /api/tasks/external/status/{task_id}?api_key=xxx` - Query task status

**External API v1** (recommended, uses header authentication):
Base URL: `/api/v1`, Authentication: `X-API-Key: sk_xxx` header

- `POST /api/v1/tasks/submit` - Submit task from external platform
- `GET /api/v1/tasks/{task_id}` - Query task status and result URL
- `POST /api/v1/tasks/{task_id}/cancel` - Cancel pending task (full refund)
- `GET /api/v1/account/info` - Query platform account balance
- `GET /api/v1/models` - List available models with prices

**Billing flow for External API v1**:
1. Task submit → freeze balance (预扣费)
2. Task success → confirm deduction, update total_spent
3. Task failed/cancelled → refund frozen amount

Platform clients are managed via admin panel (`platform.py` router) or `/api/admin/platforms` endpoints.

## WebSocket Protocol

WebSocket endpoint: `/ws/{token}/{node_id}`

### Server → Client Messages
- `{"type": "connected", "node_id": "...", "status": "idle"}` - Connection confirmed
- `{"type": "new_task", "task": {...}}` - Task dispatch
- `{"type": "ping"}` - Heartbeat request (respond with `{"type": "pong"}`)
- `{"type": "kicked", "reason": "..."}` - Forced disconnect

### Client → Server Messages
- `{"type": "pong"}` - Heartbeat response
- `{"type": "status_update", "status": "idle|busy"}` - Node status change
- `{"type": "task_result", "task_id": "...", "status": "success|failed", "result_url": "...", "proof": {...}}` - Task completion

## Proof Data Structure

Task proof is stored in `PluginTask.proof_data` as JSON:
```json
{
  "ai_task_id": "grok_abc123",
  "request_time": 1234567890,
  "response_time": 1234568090,
  "video_url_original": "https://grok-cdn.../abc.mp4",
  "status_checks": [{"time": 1234567900, "status": "processing"}],
  "download_time": 1234568150,
  "upload_time": 1234568200,
  "video_size": 25600000
}
```

## Dispatcher Strategies

Located in `backend/engines/dispatcher.py`:
- **RandomStrategy**: Random selection from available nodes
- **BestNodeStrategy**: Weighted scoring based on success_rate (0.5), speed (0.3), stability (0.2)

Strategy is configurable via `plugin_system_config` table with key `dispatcher_strategy`.

## Storage (COS)

COS service in `backend/services/cos_service.py` handles:
- Temporary upload credentials (5-min expiry, bound to task_id)
- File validation via HTTP Range requests (file header inspection)
- Signed URLs for result access

Configure via `plugin_storage_buckets` table. If no default bucket configured, falls back to local `/uploads` directory.

## Platform Client System

External platforms (e.g., Hi-Tom-AI) can consume the API as "platform clients":

1. Admin creates platform client via `/api/admin/platforms` → generates `client_id` and `api_key` (format: `sk_xxx`)
2. Platform calls `/api/v1/*` endpoints with `X-API-Key` header
3. Each task submission freezes balance; success confirms deduction; failure/cancel refunds
4. Admin can recharge platform balance, view transactions/call logs

Key components:
- `PlatformClient` model - balance tracking, status, IP whitelist
- `BillingService` - freeze_balance, confirm_deduction, refund_frozen, recharge
- `APIKeyAuth` middleware - validates X-API-Key header, checks account status/IP whitelist
- Integration docs: `docs/hi-tom-ai-integration.md`

## Testing

No test framework is configured. There are no tests in this project.