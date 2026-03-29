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
npm run dev                 # Development server
npm run build               # Production build
npm run preview             # Preview production build locally
```

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

Options: `'development'` (localhost:8000) or `'production'` (shareyouai.winepipeline.com:8082)

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
  - `tasks.py` - Task submission, results, external API
  - `admin.py` - Admin dashboard, user/node/model management
- `websocket.py` - WebSocket connection manager for real-time node communication
- `services/` - External service integrations:
  - `cos_service.py` - Tencent COS cloud storage (file upload, signed URLs)
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
- `content/index.js` - Content script that intercepts fetch requests on AI pages to capture proof data
- `popup/` - Extension popup UI
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

## Upload Limits

- Nginx: `client_max_body_size 50M` (configured in nginx.conf)
- COS credentials: 5-minute expiry, bound to task_id

## API Authentication

- User endpoints: Bearer token in Authorization header
- Admin endpoints: `user_id` query parameter (simplified auth for admin panel)
- External API: `api_key` query parameter validated against `external_api_key` system config

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