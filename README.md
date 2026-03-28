# ShareYourAi

分布式 AI 内容生成节点调度平台。

## 项目简介

ShareYourAi 是一个"滴滴模式"的 AI 内容生成平台：

- **需求方**：通过 Hi-Tom-AI 等平台提交 AI 生成任务
- **节点方**：运行浏览器插件，操作 AI 网页完成生成，获得收益
- **平台方**：调度任务、结算收益、赚取差价

## 核心功能

- 多节点并行处理
- 智能派单策略（随机/优胜略汰）
- 多 AI 模型支持（Grok、Sora、Banana Pro 等）
- 节点收益结算与提现

## 文档

详细设计文档请查看：[docs/design.md](docs/design.md)

## 项目结构

```
ShareYourAi/
├── backend/          # 后端服务 (FastAPI)
├── admin-web/        # 管理后台前端 (Vue 3)
├── plugin/           # 浏览器插件 (Chrome Extension)
└── docs/             # 文档
```

## 快速开始

```bash
# 后端
cd backend
pip install -r requirements.txt
python init_db.py
uvicorn main:app --reload --port 8001

# 管理后台
cd admin-web
npm install
npm run dev
```

## 技术栈

- **后端**: FastAPI + SQLAlchemy + Redis
- **前端**: Vue 3 + Element Plus
- **插件**: Chrome Extension Manifest V3
- **存储**: 腾讯云 COS