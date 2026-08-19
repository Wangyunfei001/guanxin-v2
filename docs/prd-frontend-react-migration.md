# 观心 v2 前端技术栈迁移增量 PRD：Vue 3 → React 19

> 版本：v2.0-frontend-migration
> 日期：2026-07-13
> 状态：Completed（当前实现为 Next.js 15 + React 19 + AI SDK）
> 作者：产品经理 许清楚
> 关联文档：[prd.md](./prd.md) | [architecture.md](./architecture.md)

---

## 1. 迁移背景与目标

### 1.1 迁移背景

观心 v2 后端（Python FastAPI + LangGraph）已完成并稳定运行（56 文件，63 测试全通过），所有 API 接口契约保持不变。当前前端使用 Vue 3 + Vite + Ant Design Vue + Pinia（38 个源文件），现决定将前端技术栈切换为 **React 19 + Next.js + AI Elements + shadcn/ui**，以获得：

- **AI 原生组件库**：AI Elements 提供 40+ AI 专用组件（流式 Markdown、工具调用可视化、推理链展示等），免去手写
- **Vercel AI SDK v5**：内置 SSE 流式处理、工具调用状态管理，替代当前手写 fetch + ReadableStream SSE 解析
- **shadcn/ui 生态**：基于 Radix UI primitives 的可定制组件，取代 Ant Design Vue 的黑盒组件
- **React 19**：并发渲染、Server Components、Actions 等新特性

**核心原则：后端完全不变，所有 API 接口契约保持不变，这是纯前端重写。**

### 1.2 产品目标

| 编号 | 目标 | 衡量标准 |
|------|------|---------|
| G-1 | 功能 1:1 迁移，零功能回退 | Vue 版 7 个页面的所有功能在 React 版中全部可用 |
| G-2 | AI 对话体验显著提升 | 流式 Markdown 实时渲染、工具调用状态可视化、推理链折叠增强 |
| G-3 | A2UI Schema 驱动架构不变 | 后端 A2UI API 契约不变，前端渲染引擎用 shadcn primitives 重写 |

### 1.3 迁移范围总览

| 范围 | 说明 |
|------|------|
| **迁移** | 全部 7 个页面、6 个 Store、7 个 API 模块、SSE 流式处理、A2UI 渲染引擎、Chat 组件、路由、布局 |
| **不迁移** | 后端所有代码、API 接口契约、数据模型、SSE 事件协议、A2UI Schema 格式 |
| **替换** | Ant Design Vue → shadcn/ui + AI Elements；Pinia → Zustand；Vue Router → Next.js App Router；手写 SSE → Vercel AI SDK / 封装 hook |

---

## 2. 当前 Vue 前端盘点（迁移基线）

### 2.1 源文件清单（38 文件）

| 分类 | 文件数 | 文件列表 |
|------|--------|---------|
| 页面 (views) | 7 | Login, Chat, KnowledgeBase, SkillMarket, AgentConfig, MCPConfig, A2UIPreview |
| 布局 | 1 | MainLayout（侧边导航 + Header + Content） |
| 状态管理 (stores) | 7 | auth, chat, knowledge, skill, agent, mcp, a2ui |
| API 模块 | 7 | client, auth, agent, knowledge, skill, mcp, a2ui |
| 组合式函数 | 1 | useSSE |
| A2UI 组件 | 6 | A2UIRenderer, FormCard, InfoCard, ListCard, ConfirmCard, ChartCard + index.ts |
| Chat 组件 | 2 | ReasoningChain, ToolCallCard |
| 类型定义 | 1 | types/index.ts |
| 路由 | 1 | router/index.ts |
| 入口/配置 | 4 | main.ts, App.vue, index.css, vite.config.ts |

### 2.2 SSE 事件协议（后端契约，不变）

当前 SSE 通过 `POST /api/agent/chat` 返回，前端使用 `fetch + ReadableStream` 手写解析。事件格式：

| 事件类型 | 数据结构 | 用途 |
|---------|---------|------|
| `token` | `{ type: 'token', content: string }` | 流式文本片段 |
| `reasoning` | `{ type: 'reasoning', content: string }` | 推理链片段 |
| `tool_call` | `{ type: 'tool_call', tool_name: string, tool_input: string }` | 工具调用开始 |
| `tool_result` | `{ type: 'tool_result', tool_output: string }` | 工具调用结果 |
| `a2ui` | `{ type: 'a2ui', schema: A2UISchema }` | A2UI schema 推送 |
| `done` | `{ type: 'done' }` | 完成 |
| `error` | `{ type: 'error', content: string }` | 错误 |

### 2.3 A2UI Catalog（后端契约，不变）

| 组件类型 | component_type | props 结构 | 当前 Vue 组件 |
|---------|---------------|-----------|-------------|
| 表单卡片 | `form_card` | `{ title, fields[], submit_text }` | FormCard.vue |
| 信息卡片 | `info_card` | `{ title, content, items[] }` | InfoCard.vue |
| 列表卡片 | `list_card` | `{ title, columns[], rows[], show_score }` | ListCard.vue |
| 确认卡片 | `confirm_card` | `{ title, message, confirm_text, cancel_text, danger }` | ConfirmCard.vue |
| 图表卡片 | `chart_card` | `{ title, chart_type, labels[], values[] }` | ChartCard.vue |

A2UIRenderer 根据 `schema.component_type` 动态分发到对应卡片组件，支持 `children[]` 递归渲染。

### 2.4 API 接口清单（后端契约，不变）

| API 模块 | 端点 | 方法 | 说明 |
|---------|------|------|------|
| auth | `/api/auth/login` | POST | 登录获取 JWT |
| auth | `/api/auth/me` | GET | 获取当前用户信息 |
| agent | `/api/agent/conversations` | GET/POST | 对话列表/创建 |
| agent | `/api/agent/conversations/:id` | GET/DELETE | 获取/删除对话 |
| agent | `/api/agent/chat` | POST (SSE) | 流式聊天 |
| knowledge | `/api/knowledge/documents/upload` | POST | 文档上传 |
| knowledge | `/api/knowledge/documents` | GET | 文档列表 |
| knowledge | `/api/knowledge/documents/:id` | GET/DELETE | 获取/删除文档 |
| knowledge | `/api/knowledge/retrieve` | POST | 检索测试 |
| skill | `/api/skills` | GET | Skill 列表 |
| skill | `/api/skills/:name` | GET | Skill 详情 |
| skill | `/api/skills/execute` | POST | 执行 Skill |
| mcp | `/api/mcp/servers` | GET/POST | MCP Server 列表/注册 |
| mcp | `/api/mcp/servers/:name` | DELETE | 删除 MCP Server |
| mcp | `/api/mcp/connect` | POST | 连接 MCP Server |
| mcp | `/api/mcp/connections` | GET | 连接列表 |
| mcp | `/api/mcp/call-tool` | POST | 调用 MCP 工具 |
| a2ui | `/api/a2ui/catalog` | GET | 组件目录 |
| a2ui | `/api/a2ui/templates` | GET | 预设模板 |
| a2ui | `/api/a2ui/preview` | POST | 预览 schema |
| a2ui | `/api/a2ui/render` | POST | 渲染模板 |
| a2ui | `/api/a2ui/render-dynamic` | POST | 动态渲染 |

---

## 3. 用户故事（迁移后体验提升）

### 3.1 对话体验增强

| 编号 | 用户故事 |
|------|---------|
| US-M-1 | As a 演示者, I want Agent 回复以流式 Markdown 实时渲染（代码高亮、表格、列表）, so that 演示内容更专业美观，而非当前的纯文本 pre 标签 |
| US-M-2 | As a 演示者, I want 工具调用展示为可视化卡片（参数折叠+结果高亮+状态图标）, so that 观众一眼理解 Agent 调用了什么工具、传了什么参数、得到什么结果 |
| US-M-3 | As a 演示者, I want 推理链以可折叠的多步骤时间线展示（每步含 Thought/Action/Observation）, so that 推理过程层次清晰，而非当前的单一文本折叠 |
| US-M-4 | As a 演示者, I want 对话消息支持复制/重新生成操作, so that 演示中可快速复用或重试 Agent 回复 |
| US-M-5 | As a 演示者, I want 输入框支持模型选择和参数提示, so that 演示时可快速切换 Agent 配置 |

### 3.2 A2UI 渲染增强

| 编号 | 用户故事 |
|------|---------|
| US-M-6 | As a 开发者, I want A2UI 卡片用 shadcn/ui primitives 重写, so that 卡片视觉风格与整体 UI 一致，而非 Ant Design Vue 的独立风格 |
| US-M-7 | As a 演示者, I want 确认卡片(ConfirmCard)在 Agent 需要用户确认时弹出交互式确认框, so that 用户可以真正点击确认/取消，而非当前的纯展示禁用按钮 |
| US-M-8 | As a 演示者, I want 图表卡片(ChartCard)使用专业图表库渲染, so that 图表更美观且支持交互（hover 提示等） |

### 3.3 开发体验提升

| 编号 | 用户故事 |
|------|---------|
| US-M-9 | As a 开发者, I want SSE 流式处理由 AI SDK 统一封装, so that 不再手写 ReadableStream 解析，减少 bug 风险 |
| US-M-10 | As a 开发者, I want 前端代码类型安全且有 IDE 自动补全, so that 开发效率更高 |

---

## 4. 需求池（P0/P1/P2 分级）

### 4.1 P0：必须迁移的核心功能（功能等价）

> **定义**：Vue 版已有的全部功能，在 React 版中必须 1:1 可用。后端 API 契约不变。

| ID | 需求描述 | 验收标准 | 对应 Vue 文件 |
|----|---------|---------|-------------|
| M-P0-001 | 项目基础设施：Next.js + TypeScript + Tailwind CSS + shadcn/ui 初始化 | `npm run dev` 启动成功，显示带侧边导航的空布局页面 | main.ts, App.vue, vite.config.ts |
| M-P0-002 | 路由系统迁移：7 个页面路由 + 登录守卫 | 未登录访问任意页面重定向到 /login；登录后可访问全部 7 个页面 | router/index.ts |
| M-P0-003 | 主布局迁移：侧边导航 + Header（用户信息/租户标签/退出）+ Content 区 | 侧边导航 6 个菜单项可切换页面；Header 显示用户名、角色、租户、退出按钮 | MainLayout.vue |
| M-P0-004 | 认证状态管理迁移：JWT token、用户信息、登录/登出、localStorage 持久化 | 登录成功后 token 存入 localStorage；刷新页面保持登录态；登出清除状态并跳转登录页 | stores/auth.ts |
| M-P0-005 | HTTP 客户端迁移：axios 实例 + JWT 请求拦截器 + 401 响应拦截器 | 所有 API 请求自动携带 Bearer Token；401 响应自动清除 token 并跳转登录页 | api/client.ts |
| M-P0-006 | 登录页迁移：用户名/密码表单 + 登录请求 + 错误提示 | 输入用户名密码可登录；登录成功跳转 /chat；错误时显示提示信息 | views/Login.vue |
| M-P0-007 | 对话列表管理：创建/列表/选择/删除对话 | 可新建对话；对话列表可点击切换；可删除对话 | stores/chat.ts (conversations 部分) |
| M-P0-008 | SSE 流式聊天：POST /api/agent/chat + 7 种事件解析 | 发送消息后流式渲染回复；推理链实时拼接；工具调用卡片显示；A2UI 卡片渲染；完成/错误状态正确 | composables/useSSE.ts, stores/chat.ts (sendMessage 部分) |
| M-P0-009 | 消息流渲染：用户消息 + 助手消息（流式文本 + 推理链 + 工具调用 + A2UI 卡片） | 助手消息可包含文本、推理链、多个工具调用、多个 A2UI 卡片；流式时显示 loading 指示 | views/Chat.vue |
| M-P0-010 | 推理链组件迁移：可折叠面板展示推理过程 | 推理链可展开/折叠；展示 Thought 内容 | components/chat/ReasoningChain.vue |
| M-P0-011 | 工具调用卡片迁移：展示工具名称、输入参数、输出结果、状态 | 工具调用时显示"执行中"；有输出后显示"已完成"；输入/输出可查看 | components/chat/ToolCallCard.vue |
| M-P0-012 | A2UI 渲染引擎迁移：根据 component_type 动态分发到对应卡片组件 | 支持 form_card/info_card/list_card/confirm_card/chart_card 五种类型；支持 children 递归 | components/a2ui/A2UIRenderer.vue |
| M-P0-013 | A2UI FormCard 迁移：表单卡片（input/select/textarea/number/switch 字段） | 5 种字段类型正确渲染；字段值和标签正确显示 | components/a2ui/FormCard.vue |
| M-P0-014 | A2UI InfoCard 迁移：信息卡片（键值对展示） | 标题、内容、items 键值对正确渲染 | components/a2ui/InfoCard.vue |
| M-P0-015 | A2UI ListCard 迁移：列表卡片（表格形式） | 列标题和数据行正确渲染；score 列带颜色标签 | components/a2ui/ListCard.vue |
| M-P0-016 | A2UI ConfirmCard 迁移：确认卡片（确认/取消按钮） | 标题、消息、确认/取消按钮正确渲染 | components/a2ui/ConfirmCard.vue |
| M-P0-017 | A2UI ChartCard 迁移：图表卡片（柱状图/折线图） | 柱状图和折线图正确渲染；坐标轴和标签正确显示 | components/a2ui/ChartCard.vue |
| M-P0-018 | A2UI 预览页迁移：组件类型选择 + 模板列表 + 实时预览 + JSON 编辑器 | 可选择 5 种组件类型预览；可加载预设模板；可编辑 JSON 并应用 | views/A2UIPreview.vue |
| M-P0-019 | 知识库管理页迁移：文档上传、文档列表、删除、切片预览、检索测试 | 可上传文档；列表显示状态和切片数；可删除文档；可查看切片；可检索测试 | views/KnowledgeBase.vue |
| M-P0-020 | Skill 市场页迁移：Skill 列表、详情查看、执行 | Skill 列表正确显示；可查看详情；可执行 Skill | views/SkillMarket.vue |
| M-P0-021 | Agent 配置页迁移：Skill 列表加载、Agent 参数 | Agent 配置页可加载 Skill 列表 | views/AgentConfig.vue |
| M-P0-022 | MCP 配置页迁移：Server 列表、注册/删除、连接、工具调用 | 可查看 Server 列表；可注册新 Server；可连接 Server；可调用工具 | views/MCPConfig.vue |
| M-P0-023 | API 模块全量迁移：auth/agent/knowledge/skill/mcp/a2ui 6 个 API 模块 | 所有 API 调用行为与 Vue 版一致，返回类型正确 | api/*.ts |
| M-P0-024 | 类型定义迁移：SSEEvent/A2UISchema/Conversation/ChatMessage/User/Document/RetrievalResult/SkillMetadata/MCPServer | 全部 TypeScript 类型在 React 项目中定义且使用 | types/index.ts |

### 4.2 P1：AI Elements 带来的体验增强

> **定义**：利用 AI Elements 组件库能力，在功能等价基础上提升交互体验。

| ID | 需求描述 | 验收标准 | AI Elements 组件 |
|----|---------|---------|-----------------|
| M-P1-001 | 流式 Markdown 实时渲染：Agent 回复以 Markdown 格式渲染（标题/列表/表格/代码块/行内代码） | 代码块有语法高亮和复制按钮；表格/列表/标题正确渲染；流式过程中实时更新 | Response + CodeBlock |
| M-P1-002 | 工具调用可视化增强：工具名称+图标、参数 JSON 折叠展示、结果高亮、状态指示器（pending/success/error） | 工具调用卡片有状态图标；参数可折叠展开；结果有语法高亮；支持多工具调用列表 | Tool |
| M-P1-003 | 推理链增强：多步骤时间线展示，每步含 Thought/Action/Observation | 推理链按步骤分组展示；每步可单独折叠；支持流式拼接时的实时更新 | Reasoning |
| M-P1-004 | 消息操作栏：复制消息内容、重新生成回复 | 每条助手消息下方有操作按钮；复制成功有提示；重新生成可触发新请求 | Actions |
| M-P1-005 | 输入框增强：支持多行输入、发送快捷键、loading 状态禁用 | Enter 发送、Shift+Enter 换行；发送中输入框禁用并显示 loading | PromptInput |
| M-P1-006 | 对话自动滚动：新消息产生时自动滚动到底部，用户上滚时不强制拉回 | 流式输出时自动滚动；用户手动上滚时暂停自动滚动；回到底部按钮 | Conversation |
| M-P1-007 | A2UI ConfirmCard 交互化：确认/取消按钮可点击并触发回调 | 用户点击确认/取消后有回调响应（P1 阶段仅前端交互，不回传 Agent） | Confirmation |
| M-P1-008 | A2UI ChartCard 使用图表库：用 recharts 替代手写 SVG | 柱状图/折线图使用 recharts 渲染；支持 hover tooltip | ChartCard (recharts) |
| M-P1-009 | 来源引用展示：知识库检索结果以来源引用卡片展示 | 检索结果有来源标注，可点击查看原文片段 | Sources |

### 4.3 P2：AI Elements 高级功能

> **定义**：AI Elements 提供的高级能力，锦上添花。

| ID | 需求描述 | 验收标准 | AI Elements 组件 |
|----|---------|---------|-----------------|
| M-P2-001 | 任务规划展示：Agent 返回 Plan 时以步骤列表展示 | Plan 步骤可勾选完成状态；展示进度 | Plan |
| M-P2-002 | 任务进度跟踪：Agent 执行多步骤任务时显示进度条 | 进度条实时更新；步骤列表可展开 | Task |
| M-P2-003 | 会话分支：从某条消息分叉出新对话 | 可在任意消息处分叉新对话；分支可切换 | Branch |
| M-P2-004 | 内嵌网页预览：Agent 返回 URL 时内嵌预览网页 | URL 可在对话内嵌 iframe 预览 | WebPreview |
| M-P2-005 | 暗色主题：支持暗色模式切换 | 主题切换后所有页面和组件正常显示 | shadcn theme |
| M-P2-006 | A2UI 表单提交回调：表单卡片提交后回传 Agent | 表单提交后发送 API 请求通知 Agent；Agent 可处理表单数据 | FormCard + API |

### 4.4 需求优先级汇总

| 优先级 | 数量 | 说明 |
|--------|------|------|
| P0 | 24 | 功能等价迁移，缺一不可 |
| P1 | 9 | AI Elements 体验增强，优先实现 |
| P2 | 6 | 高级功能，时间允许即做 |

---

## 5. AI Elements × A2UI Catalog 整合策略

### 5.1 架构分层策略

```
┌─────────────────────────────────────────────────────┐
│                    对话界面 (Chat Page)               │
│  ┌─────────────────────────────────────────────────┐ │
│  │          AI Elements Chat 层 (替代手写)          │ │
│  │  Conversation (容器+自动滚动)                     │ │
│  │  Message (消息气泡+头像)                          │ │
│  │  Response (流式 Markdown 实时渲染)                │ │
│  │  PromptInput (高级输入框+模型选择)                │ │
│  │  Reasoning (推理过程展示)                         │ │
│  │  Tool (工具调用可视化)                             │ │
│  │  Actions (复制/重新生成)                          │ │
│  └─────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────┐ │
│  │        A2UI Catalog 渲染层 (Schema 驱动, 保留)    │ │
│  │  A2UIRenderer (动态分发引擎, 不变)                │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐         │ │
│  │  │ FormCard │ │ InfoCard │ │ ListCard │  ← shadcn │ │
│  │  └──────────┘ └──────────┘ └──────────┘  primitives│ │
│  │  ┌────────────┐ ┌──────────┐                     │ │
│  │  │ConfirmCard │ │ ChartCard│  ← AI Elements      │ │
│  │  └────────────┘ └──────────┘    Confirmation      │ │
│  └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

### 5.2 Chat UI 层：AI Elements 替代手写组件

| 当前 Vue 手写组件 | 迁移到 AI Elements | 策略说明 |
|------------------|-------------------|---------|
| Chat.vue 消息列表 (v-for messages) | `<Conversation>` + `<Message>` | AI Elements 的 Conversation 组件内置自动滚动、消息分组，替代手写 div 列表 |
| 纯文本 pre 标签渲染 | `<Response>` | AI Elements 的 Response 组件支持流式 Markdown 实时渲染，替代 `<pre>` |
| 手写输入框 + 发送按钮 | `<PromptInput>` | AI Elements 的 PromptInput 支持多行、快捷键、模型选择 |
| ReasoningChain.vue (a-collapse) | `<Reasoning>` | AI Elements 的 Reasoning 组件支持多步骤时间线，替代单文本折叠 |
| ToolCallCard.vue (a-card) | `<Tool>` | AI Elements 的 Tool 组件支持参数/结果/状态可视化 |
| 无 | `<Actions>` | 新增：复制/重新生成操作栏 |
| 无 | `<CodeBlock>` | 新增：代码块语法高亮+复制 |

### 5.3 A2UI Catalog 层：Schema 驱动架构保留，卡片用 shadcn primitives 重写

**核心原则：A2UIRenderer 的分发逻辑不变（根据 `component_type` 动态分发），但底层卡片组件从 Ant Design Vue 替换为 shadcn/ui primitives。**

| A2UI 组件 | Vue 版 (Ant Design Vue) | React 版 (shadcn/ui) | 说明 |
|-----------|------------------------|----------------------|------|
| A2UIRenderer | `<component :is>` 动态组件 | React 组件映射 Map + 条件渲染 | 分发逻辑一致，实现方式不同 |
| FormCard | a-card + a-form + a-input/select/textarea/number/switch | shadcn Card + Form + Input/Select/Textarea/NumberField/Switch | 字段类型映射不变 |
| InfoCard | a-card + a-descriptions | shadcn Card + 自定义 key-value 布局 | 结构一致 |
| ListCard | a-card + a-table | shadcn Card + Table | 表格渲染一致 |
| ConfirmCard | a-card + a-space + a-button | **见 5.4 节详细分析** | 需特殊处理 |
| ChartCard | a-card + 手写 SVG | shadcn Card + recharts | 图表库替换 |

### 5.4 ConfirmCard × AI Elements Confirmation 的关系

| 维度 | A2UI ConfirmCard | AI Elements Confirmation |
|------|-----------------|------------------------|
| 触发来源 | Agent 通过 SSE `a2ui` 事件推送 schema | 前端在工具执行前弹出确认 |
| 数据来源 | `{ component_type: 'confirm_card', props: { title, message, confirm_text, cancel_text, danger } }` | 前端控制，由工具调用配置触发 |
| 交互性 | Vue 版：按钮 disabled（纯展示） | AI Elements：可交互确认/取消 |
| 回调 | 无（P0 仅展示） | 有（确认/取消触发回调） |

**整合决策**：

- **P0**：ConfirmCard 保留 A2UI Schema 驱动架构，用 shadcn Button 渲染确认/取消按钮，但按钮仍为展示态（disabled），与 Vue 版行为一致
- **P1**：ConfirmCard 按钮启用交互，点击确认/取消后触发前端回调（不回传 Agent），参考 AI Elements Confirmation 的交互模式
- **P2**：考虑将 ConfirmCard 的确认操作回传 Agent（需后端 API 支持）

**不直接使用 AI Elements Confirmation 替代 ConfirmCard**，因为两者触发机制不同：
- ConfirmCard 是 Agent 主动推送的声明式 UI（Schema 驱动）
- Confirmation 是前端在工具执行前弹出的交互式确认（代码驱动）

### 5.5 ToolCallCard × AI Elements Tool 的关系

| 维度 | A2UI ToolCallCard | AI Elements Tool |
|------|------------------|-----------------|
| 数据来源 | SSE `tool_call` + `tool_result` 事件 | Vercel AI SDK 的 tool calling 状态 |
| 展示内容 | 工具名称 + 输入参数 + 输出结果 + 状态 | 工具名称 + 参数 + 结果 + 状态 + 图标 |
| 状态管理 | 手动拼接（tool_call 时 push，tool_result 时更新 output） | AI SDK 内置状态机 |

**整合决策**：

- **P0**：ToolCallCard 用 AI Elements `<Tool>` 组件替代，但数据源仍为 SSE 事件手动解析（因为后端 SSE 协议不变，不是 Vercel AI SDK 原生协议）
- **P1**：考虑在 SSE 解析层做适配，将 `tool_call`/`tool_result` 事件映射为 AI SDK Tool 的状态对象，实现更自然的集成
- 工具调用的数据结构保持不变：`{ name, input, output?, status }`

### 5.6 SSE 流式处理迁移策略

| 维度 | Vue 版 | React 版 | 说明 |
|------|--------|----------|------|
| 传输方式 | fetch + ReadableStream 手写 | fetch + ReadableStream 封装为 hook | 底层不变，封装方式变化 |
| 解析方式 | 手写按行分割 + JSON.parse | 封装为 `useChatStream` hook | 逻辑一致，可维护性提升 |
| 事件分发 | switch-case in store | switch-case in hook callback | 逻辑一致 |
| 状态更新 | Pinia store ref 直接修改 | Zustand store setState | 模式不同但逻辑一致 |

**决策**：不使用 Vercel AI SDK 的 `useChat` hook 原生 SSE 协议（因为后端 SSE 事件格式是自定义的 `{ type, content, ... }`，不是 AI SDK 的 `data: { text: "..." }` 格式），而是：

1. 保留 `fetch + ReadableStream` 底层实现
2. 封装为 `useChatStream` React hook（等价于 Vue 的 `useSSE` composable）
3. SSE 事件解析逻辑 1:1 迁移
4. 解析后的事件通过 Zustand store 更新状态

---

## 6. 技术栈对照表

### 6.1 框架与核心库

| 维度 | Vue 版 (当前) | React 版 (目标) | 说明 |
|------|-------------|---------------|------|
| 框架 | Vue 3.5 | React 19 | 框架切换 |
| 元框架 | Vite (SPA) | Next.js 15 (App Router) | 使用 App Router 的 file-based routing |
| 语言 | TypeScript 5.6 | TypeScript 5.6 | 不变 |
| UI 组件库 | Ant Design Vue 4.2 | shadcn/ui + AI Elements | 组件库切换 |
| CSS 方案 | Ant Design 内置样式 | Tailwind CSS 4 + CSS variables | 样式方案切换 |
| 状态管理 | Pinia 2.3 | Zustand 5 | 轻量状态管理，API 风格相似 |
| HTTP 客户端 | axios 1.7 | axios 1.7 (保留) 或 native fetch | 可保留 axios，拦截器逻辑迁移 |
| 路由 | Vue Router 4.5 | Next.js App Router (file-based) | 路由方案切换 |
| 日期处理 | dayjs 1.11 | dayjs 1.11 (保留) | 不变 |
| Markdown 渲染 | 无（纯文本 pre） | react-markdown + remark-gfm + rehype-highlight | AI Elements Response 内置或配套 |
| 图表 | 手写 SVG | recharts | ChartCard 使用 |
| 图标 | @ant-design/icons-vue | lucide-react | shadcn/ui 默认图标库 |

### 6.2 状态管理映射

| Pinia Store (Vue) | Zustand Store (React) | 状态字段 | 说明 |
|-------------------|----------------------|---------|------|
| `useAuthStore` | `useAuthStore` | token, user, isLoggedIn, isAdmin | 字段和方法 1:1 迁移 |
| `useChatStore` | `useChatStore` | conversations, currentConversationId, messages, loading | messages 结构需适配 React |
| `useKnowledgeStore` | `useKnowledgeStore` | documents, loading | 1:1 迁移 |
| `useSkillStore` | `useSkillStore` | skills, loading | 1:1 迁移 |
| `useAgentStore` | `useAgentStore` | skills, loading | 1:1 迁移 |
| `useMcpStore` | `useMcpStore` | servers, connections, loading | 1:1 迁移 |
| `useA2uiStore` | `useA2uiStore` | componentTypes, templates, currentSchema | 1:1 迁移 |

### 6.3 组合式函数映射

| Composable (Vue) | Hook (React) | 说明 |
|-----------------|-------------|------|
| `useSSE()` | `useChatStream()` | SSE 流式读取，封装为 React hook |
| `useA2UI()` | 内联在 A2UIRenderer 组件中 | React 中不需要单独 hook |
| `useTenant()` | `useAuthStore` 内的 tenant 信息 | 租户信息已在 auth store 中 |

### 6.4 组件映射

| Vue 组件 | React 组件 | 迁移策略 |
|---------|-----------|---------|
| MainLayout.vue | `app/layout.tsx` | Next.js 根布局 |
| Login.vue | `app/login/page.tsx` | 页面组件 |
| Chat.vue | `app/chat/page.tsx` | 页面组件 |
| KnowledgeBase.vue | `app/knowledge/page.tsx` | 页面组件 |
| SkillMarket.vue | `app/skills/page.tsx` | 页面组件 |
| AgentConfig.vue | `app/agent/page.tsx` | 页面组件 |
| MCPConfig.vue | `app/mcp/page.tsx` | 页面组件 |
| A2UIPreview.vue | `app/a2ui/page.tsx` | 页面组件 |
| ReasoningChain.vue | AI Elements `<Reasoning>` | 用 AI Elements 替代 |
| ToolCallCard.vue | AI Elements `<Tool>` | 用 AI Elements 替代 |
| A2UIRenderer.vue | `components/a2ui/A2UIRenderer.tsx` | 分发逻辑迁移 |
| FormCard.vue | `components/a2ui/FormCard.tsx` | shadcn primitives 重写 |
| InfoCard.vue | `components/a2ui/InfoCard.tsx` | shadcn primitives 重写 |
| ListCard.vue | `components/a2ui/ListCard.tsx` | shadcn primitives 重写 |
| ConfirmCard.vue | `components/a2ui/ConfirmCard.tsx` | shadcn primitives 重写 |
| ChartCard.vue | `components/a2ui/ChartCard.tsx` | recharts 重写 |

### 6.5 API 模块映射

| Vue API 模块 | React API 模块 | 迁移策略 |
|-------------|---------------|---------|
| `api/client.ts` (axios + 拦截器) | `lib/api/client.ts` (axios + 拦截器) | 拦截器逻辑 1:1 迁移 |
| `api/auth.ts` | `lib/api/auth.ts` | 方法签名不变 |
| `api/agent.ts` | `lib/api/agent.ts` | chat() 方法保留 fetch 调用 |
| `api/knowledge.ts` | `lib/api/knowledge.ts` | 方法签名不变 |
| `api/skill.ts` | `lib/api/skill.ts` | 方法签名不变 |
| `api/mcp.ts` | `lib/api/mcp.ts` | 方法签名不变 |
| `api/a2ui.ts` | `lib/api/a2ui.ts` | 方法签名不变 |

---

## 7. 不做什么（明确排除项）

| 编号 | 排除项 | 理由 |
|------|--------|------|
| EX-1 | 不修改后端任何代码 | 后端已稳定运行，63 测试全通过 |
| 不修改 API 接口契约 | API 接口路径、请求/响应格式、SSE 事件协议全部保持不变 |
| EX-3 | 不使用 Vercel AI SDK 的 `useChat` 原生协议 | 后端 SSE 是自定义格式 `{ type, content }`，非 AI SDK 格式；仅使用 AI Elements 的 UI 组件 |
| EX-4 | 不做 SSR / Server Components | Demo 项目，纯客户端渲染 (CSR)，Next.js 仅用 App Router 做路由 |
| EX-5 | 不做 PWA / 离线支持 | Demo 项目，不需要离线能力 |
| EX-6 | 不做 i18n 国际化 | Demo 项目，中文界面 |
| EX-7 | 不做移动端深度适配 | Demo 以桌面演示为主，仅保证基本响应式 |
| EX-8 | 不做完整的权限管理 UI | 保持 Vue 版的 admin/user 基础展示 |
| EX-9 | 不做 A2UI Dynamic Schema 的前端组件编排器 | P2 功能，当前仅支持 Fixed Schema 渲染 |
| EX-10 | 不修改 A2UI Schema 格式 | 后端 Schema 格式不变，前端仅适配渲染 |
| EX-11 | 不引入 Vercel AI SDK 的流式协议适配层 | 保持 fetch + ReadableStream 手写解析，仅封装为 hook |
| EX-12 | 不保留 Vue 版前端代码 | 完全替换，不维护双版本 |

---

## 8. 待确认问题

| 编号 | 问题 | 影响范围 | 建议方向 |
|------|------|---------|---------|
| Q-M-1 | Next.js App Router 还是 Pages Router？ | 路由、布局 | 建议 App Router：layout.tsx 天然适配 MainLayout 嵌套布局，且 AI Elements 基于 App Router 设计 |
| Q-M-2 | axios 还是 native fetch？HTTP 客户端保留 axios 还是切换到 fetch？ | API 模块 | 建议保留 axios：拦截器逻辑成熟，迁移成本低；如需更轻量可后续替换 |
| Q-M-3 | AI Elements 组件库的获取方式：npm 包还是复制源码到项目？ | 依赖管理 | 建议复制源码到 `components/ai-elements/`：shadcn/ui 的哲学是 "copy-paste" 而非 npm 依赖，便于定制 |
| Q-M-4 | Zustand 还是 React Context 做状态管理？ | 状态管理 | 建议 Zustand：API 与 Pinia 相似（store + actions），迁移成本低；Context 在频繁更新场景有性能问题 |
| Q-M-5 | SSE 解析是否需要适配为 Vercel AI SDK 格式以使用 `useChat`？ | SSE 流式 | 建议不做适配：后端 SSE 格式自定义且稳定，适配层增加复杂度且可能引入 bug；封装为 `useChatStream` hook 即可 |
| Q-M-6 | ChartCard 用 recharts 还是其他图表库（如 visx）？ | A2UI ChartCard | 建议 recharts：API 简单、文档完善、与 shadcn/ui 风格一致；仅需要柱状图和折线图，recharts 足够 |
| Q-M-7 | A2UI ConfirmCard 在 P1 启用交互后，确认/取消的回调如何处理？ | A2UI 交互 | 建议 P1 仅前端交互（如显示 toast 提示），P2 再考虑回传 Agent（需后端新增 API 端点） |
| Q-M-8 | 暗色主题 (P2) 是 shadcn/ui 内置的还是需要额外配置？ | 主题 | shadcn/ui 内置暗色模式支持（通过 CSS variables + `.dark` class），实现成本低，可考虑提为 P1 |
| Q-M-9 | 知识库管理页的切片预览当前在 Vue 版中是否有独立组件？ | 知识库页 | 需确认 Vue 版 KnowledgeBase.vue 是否已包含切片预览（当前盘点未见独立 ChunkPreview 组件），可能内联在页面中 |
| Q-M-10 | Agent 配置页当前实际功能范围？Vue 版 stores/agent.ts 仅加载 Skill 列表 | Agent 配置 | 需确认 AgentConfig.vue 的完整功能：是否包含 system prompt 编辑、工具选择、模型参数配置，还是仅 Skill 列表展示 |

---

## 附录 A：React 版目标目录结构

```
frontend-react/
├── package.json
├── next.config.ts
├── tsconfig.json
├── tailwind.config.ts
├── components.json                  # shadcn/ui 配置
├── .env.example
├── src/
│   ├── app/                         # Next.js App Router
│   │   ├── layout.tsx               # 根布局（等价 MainLayout）
│   │   ├── page.tsx                 # 首页 → 重定向到 /chat
│   │   ├── login/
│   │   │   └── page.tsx             # 登录页
│   │   ├── chat/
│   │   │   └── page.tsx             # 对话界面
│   │   ├── knowledge/
│   │   │   └── page.tsx             # 知识库管理
│   │   ├── skills/
│   │   │   └── page.tsx             # Skill 市场
│   │   ├── agent/
│   │   │   └── page.tsx             # Agent 配置
│   │   ├── mcp/
│   │   │   └── page.tsx             # MCP 配置
│   │   └── a2ui/
│   │       └── page.tsx             # A2UI 预览
│   ├── components/
│   │   ├── ui/                      # shadcn/ui primitives
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── input.tsx
│   │   │   ├── select.tsx
│   │   │   ├── table.tsx
│   │   │   ├── form.tsx
│   │   │   ├── switch.tsx
│   │   │   ├── textarea.tsx
│   │   │   ├── number-field.tsx
│   │   │   └── ...
│   │   ├── ai-elements/             # AI Elements 组件
│   │   │   ├── conversation.tsx
│   │   │   ├── message.tsx
│   │   │   ├── response.tsx
│   │   │   ├── prompt-input.tsx
│   │   │   ├── reasoning.tsx
│   │   │   ├── tool.tsx
│   │   │   ├── actions.tsx
│   │   │   ├── code-block.tsx
│   │   │   ├── sources.tsx
│   │   │   └── ...
│   │   ├── a2ui/                    # A2UI Catalog 渲染组件
│   │   │   ├── A2UIRenderer.tsx     # 动态渲染引擎
│   │   │   ├── FormCard.tsx         # 表单卡片 (shadcn primitives)
│   │   │   ├── InfoCard.tsx         # 信息卡片 (shadcn primitives)
│   │   │   ├── ListCard.tsx         # 列表卡片 (shadcn primitives)
│   │   │   ├── ConfirmCard.tsx      # 确认卡片 (shadcn primitives)
│   │   │   └── ChartCard.tsx        # 图表卡片 (recharts)
│   │   └── layout/
│   │       ├── SideNav.tsx          # 侧边导航
│   │       └── Header.tsx           # 顶部导航栏
│   ├── lib/
│   │   ├── api/                     # API 客户端模块
│   │   │   ├── client.ts            # axios 实例 + 拦截器
│   │   │   ├── auth.ts              # 认证 API
│   │   │   ├── agent.ts             # Agent API (含 SSE fetch)
│   │   │   ├── knowledge.ts         # 知识库 API
│   │   │   ├── skill.ts             # Skill API
│   │   │   ├── mcp.ts               # MCP API
│   │   │   └── a2ui.ts              # A2UI API
│   │   ├── stores/                  # Zustand 状态管理
│   │   │   ├── auth.ts              # 认证状态
│   │   │   ├── chat.ts              # 对话状态
│   │   │   ├── knowledge.ts         # 知识库状态
│   │   │   ├── skill.ts             # Skill 状态
│   │   │   ├── agent.ts             # Agent 配置状态
│   │   │   ├── mcp.ts               # MCP 状态
│   │   │   └── a2ui.ts              # A2UI 状态
│   │   ├── hooks/                   # React Hooks
│   │   │   └── useChatStream.ts     # SSE 流式处理 (等价 useSSE)
│   │   └── utils.ts                 # 工具函数 (cn 等)
│   ├── types/
│   │   └── index.ts                 # TypeScript 类型定义 (1:1 迁移)
│   └── globals.css                  # 全局样式 (Tailwind + CSS variables)
```

---

## 附录 B：SSE 事件 → UI 组件映射

| SSE 事件 | 数据处理 | UI 渲染 | AI Elements 组件 |
|---------|---------|--------|-----------------|
| `token` | 拼接到当前消息 `content` | `<Response>` 流式 Markdown 渲染 | Response |
| `reasoning` | 拼接到当前消息 `reasoning` | `<Reasoning>` 折叠展示 | Reasoning |
| `tool_call` | push 到 `toolCalls[]`（name + input） | `<Tool>` 展示工具名+参数，状态=pending | Tool |
| `tool_result` | 更新最后一个 toolCall 的 `output` | `<Tool>` 展示结果，状态=success | Tool |
| `a2ui` | push 到 `a2uiSchemas[]` | `<A2UIRenderer>` 按 schema 渲染卡片 | A2UIRenderer (自定义) |
| `done` | 设置 `streaming = false` | 移除 loading 指示 | - |
| `error` | 设置错误消息 | 显示错误内容 + `<Actions>` 重新生成 | Actions |

---

*本文档为 Draft 状态，待团队评审后定稿。下一步交由架构师高见远进行 React 前端架构设计与任务分解。*
