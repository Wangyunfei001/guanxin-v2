# 观心 v2

观心 v2 是一个面向稳定演示的多租户 AI Agent 全栈项目。当前主链路使用 FastAPI、LangGraph、SQLite、ChromaDB、Next.js 15、React 19、AI SDK 与 assistant-ui。

## 当前能力

- JWT / API Key 认证与租户隔离
- 文档上传、解析、切片、向量检索和 SQLite 元数据持久化
- AI SDK 流式 Assistant、会话侧栏和完整历史恢复
- 文本、推理、工具输入/输出、A2UI 与 approval 状态持久化
- 内置文本摘要、数据分析及管理型 Skill
- stdio MCP 客户端与天气示例 Server
- 统一 Supervisor、RBAC Tool Catalog 与最多 4 回合 / 8 次调用的只读 Tool Loop
- DeepSeek Web Search 驱动的快速 / 深度研究，支持来源、预算、取消与重启恢复
- 租户级 Agent 配置；admin 可编辑，普通用户只读
- API、SkillExecutor 与 Agent 工具三层 RBAC
- 最多 16 步的持久化线性工作流，支持参数表单、审批、取消和故障接管
- LangGraph interrupt/resume 与独立 SQLite checkpoint，刷新或重启后可继续

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.11+、FastAPI、LangGraph、原生 sqlite3 |
| 前端 | Next.js 15、React 19、TypeScript、AI SDK、assistant-ui |
| 数据 | SQLite（业务数据）、SQLite checkpoint、ChromaDB（向量）、users.json（账号） |
| 工具协议 | MCP stdio、A2UI data parts |

## 快速开始

环境要求：Python 3.11+、Node.js 18+、Ollama（本地 Embedding）。

首次启动前准备本地向量模型：

```bash
ollama pull bge-m3
ollama serve
```

```bash
./scripts/start.sh
```

也可以分别启动：

```bash
./scripts/start.sh backend
./scripts/start.sh frontend
```

手动启动后端：

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
python -m uvicorn app.main:app --reload --port 8000
```

手动启动前端：

```bash
cd frontend-react
npm install
npm run dev
```

访问地址：

- 前端：http://localhost:3000
- 后端：http://localhost:8000
- OpenAPI：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

## 配置

后端配置位于 `backend/.env`。重要配置：

```dotenv
DATABASE_PATH=./data/guanxin.db
CHECKPOINT_DATABASE_PATH=./data/guanxin-checkpoints.db
CHROMA_PERSIST_DIR=./data/chroma
UPLOAD_DIR=./data/uploads
OPENAI_API_KEY=
OPENAI_API_BASE=https://api.deepseek.com
OPENAI_MODEL=deepseek-v4-pro
RESEARCH_MODEL=deepseek-v4-flash
EMBEDDING_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
EMBEDDING_MODEL=bge-m3:latest
EMBEDDING_DIMENSION=1024
```

普通 Agent 通过 DeepSeek V4 Pro 的 OpenAI 兼容接口工作；Research 使用 V4 Flash Responses API 与内置 Web Search。知识库使用本机 `bge-m3:latest`
生成 1024 维向量。Ollama 不可用时会明确报错，不会写入随机向量。
自动化测试会 mock 外部模型调用。

## 预设账号

| 用户名 | 密码 | 租户 | 角色 |
|---|---|---|---|
| admin | admin123 | tenant-a | admin |
| user | user123 | tenant-a | user |
| demo | demo123 | tenant-b | admin |

业务权限基线：所有登录用户可管理本租户知识库、使用文本摘要/数据分析、读取 Agent 配置并调用已连接 MCP 工具；只有 admin 可修改 Agent 配置、管理 MCP、管理用户、导出数据和执行系统诊断。

## 核心 API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/login` | 登录 |
| POST | `/api/knowledge/documents/upload` | 上传文档 |
| POST | `/api/knowledge/retrieve` | 检索知识库 |
| POST | `/api/agent/conversations` | 创建会话 |
| GET | `/api/agent/conversations/{id}` | 获取完整历史 parts |
| POST | `/api/agent/chat/aisdk` | 认证后的 AI SDK UIMessage 流 |
| GET | `/api/agent/research/{run_id}` | 获取研究阶段、预算、任务、来源与报告 |
| POST | `/api/agent/research/{run_id}/cancel` | 取消自己的研究运行 |
| POST | `/api/agent/research/{run_id}/resume` | 手动恢复重启后 interrupted 的研究 |
| GET | `/api/agent/workflows/{run_id}` | 获取工作流计划、步骤、中断与结果 |
| POST | `/api/agent/workflows/{run_id}/cancel` | 取消自己的等待中工作流 |
| POST | `/api/agent/workflows/{run_id}/resolve` | admin 接管不确定的风险步骤 |
| GET / PUT | `/api/agent/config` | 读取 / admin 更新 Agent 配置 |
| POST | `/api/mcp/connect` | 连接并为当前租户 Agent 幂等启用 Server |
| PUT | `/api/mcp/servers/{server}/tools/{tool}/policy` | admin 标注 MCP 工具风险 |
| POST | `/api/a2ui/preview` | 使用 `{ "schema": ... }` 预览 |

AI SDK 是唯一聊天协议；历史 AG-UI 与自定义 SSE 端点已移除。

## 验证

```bash
cd backend
source .venv/bin/activate
pytest -q

cd ../frontend-react
npm run lint
npx tsc --noEmit
npm run build
npm run test:e2e
```

当前测试覆盖 SQLite 幂等与重启持久、外键级联、并发写、租户/用户隔离、RBAC、A2UI 契约、Agent 配置、Supervisor 路由、结构化工具 Schema、稳定 tool call、Research 来源去重与持久化、工作流 interrupt/resume、风险步骤故障接管及幂等执行。

## 数据与初始化

首次启动会幂等创建两份示例文档、每个预设租户的默认 Agent 配置和天气 MCP 配置。Agent 配置采用 absent-only seed，重启不会覆盖管理员修改。

需要重置演示数据时，只清理以下业务目录/文件；`backend/data/users.json` 是账号来源，应保留：

- `backend/data/uploads/`
- `backend/data/chroma/`
- `backend/data/guanxin.db` 及其 sidecar
- `backend/data/guanxin-checkpoints.db` 及其 sidecar

## 已知边界

- 当前目标是本地稳定演示，不包含生产部署、审计日志、限流或远程 MCP SSE。
- 用户账号本轮继续保存在 `users.json`。
- MCP 当前为本地 stdio 连接。
- 内置天气 Server 只返回随机模拟数据，不代表实时天气。
- Deep Research 只使用公开网页和当前租户授权的只读能力；不会访问登录态网页或调用写工具。
- 工作流当前只支持线性计划，不支持条件分支、并行 DAG 或分布式执行。
- 本地 Ollama 必须在后端启动前可用；当 `bge-m3:latest` 不可用时，知识库不会退化为随机向量。
