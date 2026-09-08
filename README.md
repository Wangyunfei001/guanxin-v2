# 观心 v2

交付版本：`v0.2.0-demo`，应用版本 `0.2.0`。发布状态与真实场景记录见 [验收报告](docs/releases/v0.2.0-demo-acceptance.md)，演示步骤见 [Demo 操作手册](docs/demo-guide.md)。

观心 v2 是一个面向稳定演示的多租户 AI Agent 全栈项目。当前开发分支已迁移为 FastAPI、Deep Agents、LangGraph、SQLite、ChromaDB、Next.js 15、React 19 与 LangChain React SDK。上方 v0.2.0 验收报告属于迁移前发布记录。

## 当前能力

- JWT / API Key 认证与租户隔离
- 文档上传、解析、切片、向量检索和 SQLite 元数据持久化
- LangChain React SDK 原生流式 Assistant、会话侧栏和 checkpoint 历史恢复
- 原生文本/工具事件、会话虚拟文件下载；旧研究与工作流记录仍可查看
- 内置文本摘要、数据分析及管理型 Skill
- stdio MCP 客户端、真实天气外部 Server，以及供外部客户端调用的只读观心网关
- Deep Agents 官方工具循环、摘要与文件上下文；业务中间件复核 RBAC，默认不启用子代理或 shell
- Deep Agents 使用授权知识库与 DeepSeek Web Search 生成研究报告，支持明确取消和中断后手动继续
- 租户级 Agent 配置；admin 可编辑，普通用户只读
- API、SkillExecutor 与 Agent 工具三层 RBAC
- 最多 16 步的持久化线性工作流，支持参数表单、审批、取消和故障接管
- LangGraph interrupt/resume 与独立 SQLite checkpoint，刷新或重启后可继续

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.11+、FastAPI、Deep Agents 0.7.13、LangGraph、原生 sqlite3 |
| 前端 | Next.js 15、React 19、TypeScript、@langchain/react 1.0.35 |
| 数据 | SQLite（业务数据）、SQLite checkpoint、ChromaDB（向量）、users.json（管理型 Skill 演示记录） |
| 工具协议 | MCP stdio、LangChain 线程 HTTP/SSE 协议 |

## 快速开始

环境要求：Python 3.11+（CI 使用 3.13）、Node.js 20+、Ollama（本地 Embedding）。

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
npm ci
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
USER_DATA_PATH=./data/users.json
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

PDF 支持提取文本层，DOCX 支持段落和表格文本；扫描 PDF/OCR 不在本轮范围内。

### 两个不同用途的 MCP Server

| Server | 方向 | 启动入口 | 能力 |
|---|---|---|---|
| 观心网关 | 外部客户端 → 观心 HTTP API | `scripts/start-mcp-server.sh` | 三个固定只读工具，API Key 绑定用户与租户 |
| 天气外部 Server | 观心 Agent → Open-Meteo | `scripts/start-weather-mcp-server.sh` | 公网真实天气查询，不需要观心 API Key |

观心网关不直接访问 SQLite/ChromaDB，不提供通用 Skill 执行器或任何写操作。

1. 先启动观心后端，通过 `POST /api/auth/login` 登录获取 JWT。
2. 携带 `Authorization: Bearer <JWT>` 调用 `GET /api/auth/api-keys`，取得当前用户的 API Key。不要把返回值提交进 Git 或公开日志。
3. 在启动 MCP 客户端的环境中设置：

```bash
export GUANXIN_API_BASE_URL=http://127.0.0.1:8000/api
read -s GUANXIN_API_KEY
export GUANXIN_API_KEY
backend/.venv/bin/python scripts/verify-mcp-server.py
```

验证脚本使用官方 Python MCP SDK 启动独立 stdio 子进程，完成 initialize、工具发现和三个调用；只打印工具名、结果数量等非敏感信息。

工具签名：`knowledge_retrieve(query, top_k=5)`、`text_summary(text, max_sentences=3)`、`data_analysis(data, analysis_type="basic")`。知识结果使用 `{"results": [...]}` 包装；`full` 分析包含图表数据。`top_k` 和 `max_sentences` 范围为 1–20。

Claude Desktop 配置示例（替换绝对路径和密钥，本示例不是已测试的 Claude Desktop 安装记录）：

```json
{
  "mcpServers": {
    "guanxin": {
      "command": "/absolute/path/guanxin-v2/scripts/start-mcp-server.sh",
      "env": {
        "GUANXIN_API_BASE_URL": "http://127.0.0.1:8000/api",
        "GUANXIN_API_KEY": "<当前用户的 API Key>"
      }
    }
  }
}
```

缺少密钥时启动失败；401/403、网络错误、超时及业务失败均返回 MCP tool error。启动诊断只写 stderr，stdout 专用于 MCP 协议。API Key 只通过 `X-API-Key` 请求头传递，错误信息脱敏。预设认证用户及 API Key 为进程内 Demo 数据，后端重启后请重新获取 Key。

### 故障排查

- MCP 无法启动：检查 `backend/.venv` 已安装依赖、脚本可执行、密钥已导出。
- MCP 认证失败：重新从当前后端获取 Key，并确认没有误用 DeepSeek Key。
- MCP 连接失败：检查 `GUANXIN_API_BASE_URL` 包含 `/api`、后端已启动。
- PDF 没有切片：确认文件包含可提取文字；扫描件需要先做 OCR。
- Research 无结果：检查 DeepSeek Responses/Web Search 可用性；单次 provider 调用最多等待 60 秒。失败、超时或中断不等于验收通过。
- 自动化端口占用：释放测试专用的 13000/18000，测试不会复用已有服务。

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
| GET | `/api/agent/threads/{id}/state` | 当前线程消息、虚拟文件与业务状态 |
| POST | `/api/agent/threads/{id}/commands` | 官方 SDK run.start 命令 |
| POST | `/api/agent/threads/{id}/stream/events` | 事件订阅与持久重放 |
| POST | `/api/agent/threads/{id}/cancel` | 显式取消任务 |
| GET | `/api/agent/threads/{id}/files/content?path=...` | 下载自己的任务文件 |
| POST | `/api/agent/workflows/{run_id}/respond` | 提交参数、批准或拒绝工作流 |
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

AI SDK 端点与前端依赖已移除。新链路使用官方 HttpAgentServerAdapter；Python v3 消息事件只做 envelope 适配（tuple → data/node），不自研消息拼接器。研究旧 API 仅为既有记录的恢复兼容保留，新任务不使用旧研究编排。

### 本轮运行边界

- 后端使用单进程 Uvicorn。启动后恢复遗留 running 状态为 interrupted；不会自动重放任务。关闭浏览器只关闭订阅，显式取消才停止后台任务。多进程 worker 调度属于后续迭代。
- 模型最多 16 次、工具最多 24 次调用、单次运行 480 秒；这是每次运行的上限，不是跨恢复的费用预算。
- Deep Agents / LangGraph v3 事件仍为实验接口，必须使用提交的锁文件；升级时重跑原生浏览器用例。
- 当前前端支持文本附件（总输入最多 100000 字符）与 Markdown 产物下载；图片/PDF 会话附件、分支编辑与 checkpoint 时间旅行未迁移。知识库的 PDF/DOCX 上传保持原有能力。
- 身份体系仍为 Demo 账号，不能将本次迁移视为生产认证改造。
- 未配置模型时明确显示失败，不返回伪造的成功报告。

## 验证

```bash
cd backend
source .venv/bin/activate
pip install -e '.[dev]'
pytest -q

cd ../frontend-react
npm run lint
npm run typecheck
npm run build
npx playwright install chromium
npm run test:e2e
GUANXIN_E2E_AGENT_FIXTURE=1 npm run test:e2e -- e2e/native-agent.spec.ts
```

完整 pytest 包含真正的 MCP stdio 协议测试；也可单独运行 `pytest tests/test_mcp_gateway.py -q`。CI 在 PR 和 main push 上运行 Python 3.13、Node 20、lint、类型检查、构建、pytest 和 Chromium E2E，不配置真实 API Key。

pytest/Playwright 使用系统临时数据目录；Playwright 的 SQLite、checkpoint、Chroma、uploads、users JSON 位于同一临时根目录，结束时精确清理。测试前端使用 `.next-e2e` 和专用端口，不访问现有开发服务。自定义本地实例可设置 `GUANXIN_BACKEND_URL`（Next.js 代理目标）及 `NEXT_DIST_DIR`（独立构建缓存）。

当前测试覆盖 SQLite 幂等与重启持久、外键级联、并发写、租户/用户隔离、RBAC、A2UI 契约、Agent 配置、Deep Agents 工具循环与恢复、结构化工具 Schema、稳定 tool call、Research 来源去重与持久化、工作流 interrupt/resume、风险步骤故障接管及幂等执行。

## 数据与初始化

首次启动会幂等创建两份示例文档、每个预设租户的默认 Agent 配置和天气 MCP 配置。Agent 配置采用 absent-only seed，重启不会覆盖管理员修改。

需要重置演示数据时，先停止对应服务并确认路径仅属于演示环境；不要清理日常开发目录。`backend/data/users.json` 是管理型 Skill 的业务记录，不是登录账号来源，应单独备份：

- `backend/data/uploads/`
- `backend/data/chroma/`
- `backend/data/guanxin.db` 及其 sidecar
- `backend/data/guanxin-checkpoints.db` 及其 sidecar

## 已知边界

- 当前目标是本地稳定演示，不包含生产部署、审计日志、限流或远程 MCP SSE。
- 登录账号/API Key 仍为进程内预设数据；管理型 Skill 的业务用户记录保存在 `users.json`，不进行账号数据库迁移。
- MCP 当前为本地 stdio 连接。
- 内置天气 MCP Server 通过 Open-Meteo 查询真实当前天气；它依赖公网可用性，不提供天气预警或商业级 SLA。
- Deep Research 只使用公开网页和当前租户授权的只读能力；不会访问登录态网页或调用写工具。
- 工作流当前只支持线性计划，不支持条件分支、并行 DAG 或分布式执行。
- 本地 Ollama 必须在后端启动前可用；当 `bge-m3:latest` 不可用时，知识库不会退化为随机向量。
