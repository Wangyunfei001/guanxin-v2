# 观心 v2 - AI Agent 全栈 Demo 系统

> 基于 LangGraph + FastAPI + Vue 3 的多租户 AI Agent 平台演示项目

## 功能概览

- **多租户知识库**：文档上传 → 自动分块 → 向量嵌入 → 语义检索，租户间数据完全隔离
- **LangGraph ReAct Agent**：推理-行动循环，支持工具调用、流式输出（SSE）
- **技能系统**：可扩展技能架构，内置数据分析、文本摘要技能，支持 DAG 编排
- **MCP 协议集成**：标准 MCP 客户端/服务端，内置天气查询示例 Server
- **A2UI 声明式 UI**：Agent 工具调用结果自动生成结构化卡片，5 种组件类型
- **JWT + API Key 双认证**：支持 Bearer Token 和 X-API-Key 两种认证方式

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.11+ / FastAPI / LangGraph / ChromaDB / MCP SDK |
| 前端 | Vue 3 / Vite / Ant Design Vue / Pinia / TypeScript |
| 向量数据库 | ChromaDB（嵌入式模式，无需额外服务） |

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+

### 一键启动

```bash
# 1. 克隆项目
cd guanxin-v2

# 2. 一键启动（自动创建虚拟环境、安装依赖、启动前后端）
./scripts/start.sh

# 或分别启动
./scripts/start.sh backend    # 仅启动后端
./scripts/start.sh frontend   # 仅启动前端
```

### 手动启动

**后端：**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env  # 编辑 .env 配置 OPENAI_API_KEY
python -m uvicorn app.main:app --reload --port 8000
```

**前端：**
```bash
cd frontend
npm install
cp .env.example .env
npx vite
```

### 访问地址

| 服务 | 地址 |
|---|---|
| 前端页面 | http://localhost:5173 |
| 后端 API | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |
| 健康检查 | http://localhost:8000/health |

## 预设账号

| 用户名 | 密码 | 租户 | 角色 |
|---|---|---|---|
| admin | admin123 | 租户A | 管理员 |
| user | user123 | 租户A | 普通用户 |
| demo | demo123 | 租户B | 管理员 |

## 演示场景

### 1. 知识库管理
- 登录后进入「知识库」页面
- 上传 txt/md/json 文件
- 文件自动解析、分块、向量化存储
- 使用检索测试验证语义搜索效果

### 2. AI 对话
- 进入「AI 对话」页面
- 新建对话，输入问题
- AI 自动检索知识库并流式返回回答
- 工具调用过程实时展示（工具名、输入、输出）
- 检索结果自动渲染为 A2UI 列表卡片

### 3. 技能市场
- 进入「技能市场」页面
- 查看已注册技能（数据分析、文本摘要）
- 点击「执行」体验技能调用
- 数据分析技能会生成 A2UI 图表卡片

### 4. A2UI 预览
- 进入「A2UI 预览」页面
- 左侧选择组件类型或预设模板
- 中间实时预览渲染效果
- 右侧编辑 JSON Schema 并应用

### 5. MCP 配置
- 进入「MCP 配置」页面
- 查看已注册的 MCP Server（内置天气查询）
- 点击「连接」建立 MCP 连接
- 连接成功后可调用 Server 上的工具

### 6. Agent 配置
- 进入「Agent 配置」页面
- 查看和修改 Agent 参数（模型、温度、提示词等）
- 配置启用的工具、技能和 MCP Server

## API 文档

启动后端后访问 http://localhost:8000/docs 查看完整的 OpenAPI 文档。

主要 API 端点：

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /api/auth/login | 用户登录 |
| GET | /api/auth/me | 获取当前用户 |
| POST | /api/knowledge/documents/upload | 上传文档 |
| GET | /api/knowledge/documents | 列出文档 |
| POST | /api/knowledge/retrieve | 检索知识库 |
| POST | /api/agent/conversations | 创建对话 |
| POST | /api/agent/chat | 发送消息（SSE 流式） |
| GET | /api/skills | 列出技能 |
| POST | /api/skills/execute | 执行技能 |
| GET | /api/mcp/servers | 列出 MCP Server |
| POST | /api/mcp/connect | 连接 MCP Server |
| GET | /api/a2ui/catalog | 获取 A2UI 组件目录 |
| GET | /api/a2ui/templates | 获取 A2UI 模板列表 |

## MCP Server 使用

### 启动内置天气 MCP Server

```bash
./scripts/start-mcp-server.sh
```

或在代码中连接：

```python
from app.mcp.client import get_mcp_client

client = get_mcp_client()
result = await client.connect(
    server_name="weather",
    command="python",
    args=["-m", "app.mcp.weather_server"],
)
```

## 测试

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v
```

测试覆盖：
- 认证 API（登录成功/失败、令牌验证、API Key 认证）
- 知识库 API（上传/列表/检索/删除、租户隔离）

## 项目结构

```
guanxin-v2/
├── backend/
│   ├── app/
│   │   ├── main.py              # 应用入口
│   │   ├── config.py            # 配置管理
│   │   ├── core/                # 核心模块
│   │   │   ├── responses.py     # 统一响应
│   │   │   ├── exceptions.py    # 异常定义
│   │   │   ├── tenant.py        # 多租户上下文
│   │   │   ├── security.py      # JWT/密码
│   │   │   ├── database.py      # ChromaDB
│   │   │   ├── deps.py          # 依赖注入
│   │   │   └── middleware.py    # 中间件
│   │   ├── models/              # 数据模型
│   │   ├── services/            # 业务服务
│   │   ├── agent/               # Agent 模块
│   │   ├── skills/              # 技能系统
│   │   ├── mcp/                 # MCP 协议
│   │   ├── a2ui/                # A2UI 声明式 UI
│   │   ├── api/                 # API 路由
│   │   └── seed/                # 种子数据
│   ├── tests/                   # 测试
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── main.ts
│   │   ├── App.vue
│   │   ├── router/              # 路由
│   │   ├── stores/              # Pinia 状态
│   │   ├── api/                 # API 客户端
│   │   ├── composables/         # 组合式函数
│   │   ├── components/          # 组件
│   │   │   ├── a2ui/            # A2UI 组件
│   │   │   └── chat/            # 聊天组件
│   │   ├── layouts/             # 布局
│   │   └── views/               # 页面
│   ├── package.json
│   └── vite.config.ts
├── scripts/                     # 启动脚本
│   ├── start.sh
│   ├── start-backend.sh
│   ├── start-frontend.sh
│   └── start-mcp-server.sh
└── README.md
```

## 开发指南

### 添加新技能

1. 在 `backend/app/skills/builtins/` 下创建新文件
2. 继承 `BaseSkill`，实现 `_define_metadata()` 和 `execute()` 方法
3. 技能会自动被 `SkillRegistry` 扫描注册

### 添加新 A2UI 组件

1. 在 `backend/app/a2ui/catalog.py` 中添加组件类型定义
2. 在 `frontend/src/components/a2ui/` 下创建 Vue 组件
3. 在 `A2UIRenderer.vue` 的 `componentMap` 中注册

### 添加新 MCP Server

1. 参考 `app/mcp/weather_server.py` 创建 MCP Server
2. 在 `app/mcp/server.py` 中注册默认配置
3. 或通过 API/MCP 配置页面动态注册

## 已知限制

- 数据存储为内存模式，重启后丢失（ChromaDB 持久化除外）
- 未配置 OPENAI_API_KEY 时 AI 对话使用模拟响应
- MCP Server 通过 stdio 通信，不支持远程连接
- A2UI 表单/确认卡片为展示模式，不支持交互提交

## License

MIT
