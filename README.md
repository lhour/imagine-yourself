# imagine yourself v3

> 基于 DeepSeek + 多存档 SQLite + FastAPI + React 的叙事游戏引擎

## 这是什么

一个 Agent 驱动的叙事游戏后端 + Web 控制台。核心能力：

- 📖 **剧本驱动** — 9+1 文件 JSONL 格式剧本，一键初始化写入 SQLite 存档
- 💾 **多存档隔离** — 每存档独立 `.db`，支持快照/恢复/主角设定
- 🧠 **19 类实体** — 角色/群体/地图/记忆/任务等，统一 CRUD + 专用方法（记忆衰减/遗忘/扭曲/宫殿展开）
- 🤖 **Agent 编排** — DeepSeek LLM + 工具系统 + 技能系统 + 上下文记忆
- 🌐 **HTTP API** — FastAPI 自动生成 Swagger/ReDoc 文档
- 🖥️ **Web 控制台** — React 18 + PixiJS + Three.js 混合渲染

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.12 · FastAPI · SQLite（多存档分库） |
| 前端 | React 18 · TypeScript · Vite 5 · PixiJS · Three.js |
| LLM | DeepSeek（OpenAI SDK 兼容） |
| 测试 | pytest（38 用例 + E2E 验证脚本） |

## 快速开始

### 1. 后端

```bash
pip install -r src/backend/requirements.txt
copy src\backend\.env.example src\backend\.env
# 编辑 src/backend/.env 填入 DEEPSEEK_API_KEY
```

### 2. 前端

```bash
cd src/frontend
npm install
npm run build    # 构建产物会被后端自动挂载
```

### 3. 启动

```bash
uvicorn src.backend.http.app:app --host 0.0.0.0 --port 8000 --reload
```

打开 http://localhost:8000 即可访问 Web 控制台，API 文档见 http://localhost:8000/docs。

> 前端开发热重载模式：`cd src/frontend && npm run dev`，访问 http://localhost:5173

## 目录概览

```
imagine-yourself/
├── src/
│   ├── backend/          # v3 后端（agent/storage/service/http/drama/saves/tests）
│   │   ├── agent/        # LLM 管线（prompts/skills/tools 配置 + pipeline）
│   │   ├── drama/        # 剧本源文件（sample/ 示例剧本）
│   │   ├── http/         # FastAPI 路由（saves/entities/memory/maps/groups/world/dramas/config/agent）
│   │   ├── service/      # 业务逻辑（drama_service/memory_service/world_service/map_service）
│   │   └── storage/       # SQLite 多存档管理 + 19 类实体 Active Record
│   └── frontend/         # v3 前端（React + PixiJS + Three.js）
├── docs/                 # 架构文档（含 v3_redesign_spec.md）
├── logs/                 # 运行日志
├── scripts/              # 工具脚本（check_env/check_db_state/test_tick 等）
└── README.md
```

## 文档

- 📐 [v3 重设计规格](docs/v3_redesign_spec.md) — v3 完整设计文档