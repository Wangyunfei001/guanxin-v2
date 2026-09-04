# 观心 v2 全功能 Demo PRD

> 版本：v0.2.0-demo
> 日期：2026-09-04
> 状态：封版验收中；以发布验收报告为准
> 作者：产品经理 许清楚

---

## 1. 产品定位与目标

### 1.1 产品定位

观心 v2 是一套**AI Agent 全栈系统的全功能 Demo**，从零实现七大模块（知识库管理、Agent 智能体、MCP 协议集成、Skill 技能系统、服务端、A2UI Catalog、前端展示层），完整展示一套 AI Agent 系统从数据导入到智能交互的全链路能力。

| 维度 | 说明 |
|------|------|
| 是什么 | 一套可本地运行的全功能演示系统，涵盖 AI Agent 全栈技术栈的七大核心模块 |
| 给谁看 | 内部技术团队（架构验证、开发参考）、外部合作方（能力展示、技术选型参考） |
| 解决什么问题 | 验证各模块技术可行性、展示模块间数据流通、提供可复用的技术参考实现 |
| 不是什么 | 不是生产级系统；不追求高可用、高并发、数据安全等生产指标 |

### 1.2 成功标准

| 编号 | 标准 | 验收方式 |
|------|------|---------|
| S-1 | 七大模块均有可交互的功能界面 | 逐模块操作验证 |
| S-2 | 知识库 → Agent → 前端的核心链路跑通 | 上传文档后可对话问答 |
| S-3 | Agent 可调用知识库检索、Skill、MCP 工具三类工具 | 对话中触发工具调用并展示推理链 |
| S-4 | A2UI 组件可由 Agent 声明式返回并前端动态渲染 | 对话中出现非纯文本的卡片式 UI |
| S-5 | MCP Server 可被外部客户端连接并调用工具 | 用 MCP 客户端（如 Claude Desktop）连接验证 |
| S-6 | 一键启动全部服务，本地开发环境即开即用 | 执行启动脚本后所有服务正常运行 |
| S-7 | 多租户数据隔离基本可用 | 不同租户的知识库和会话互不可见 |

---

## 2. 用户故事

### 2.1 知识库管理

| 编号 | 用户故事 |
|------|---------|
| US-KB-1 | As a 开发者, I want 上传 PDF/Markdown/TXT/DOCX 文档并自动切片和向量化, so that 知识库可快速构建且无需手动预处理 |
| US-KB-2 | As a 演示者, I want 在管理面板预览切片结果并调整 chunk 参数, so that 我能向观众展示切片策略的效果差异 |
| US-KB-3 | As a 开发者, I want 对知识库执行检索测试并查看 score, so that 我能验证检索质量并调优参数 |

### 2.2 Agent 智能体

| 编号 | 用户故事 |
|------|---------|
| US-AG-1 | As a 演示者, I want 与 Agent 多轮对话并看到流式输出, so that 演示自然流畅不卡顿 |
| US-AG-2 | As a 演示者, I want 看到 Agent 的推理链（Thought → Action → Observation）, so that 向观众展示 Agent 的思考过程而非黑盒 |
| US-AG-3 | As a 开发者, I want 配置 Agent 的 system prompt 和工具集, so that 我能快速切换不同 Agent 人设和能力范围 |

### 2.3 MCP 协议集成

| 编号 | 用户故事 |
|------|---------|
| US-MCP-1 | As a 开发者, I want 将本系统的知识库检索暴露为 MCP 工具, so that 外部 MCP 客户端（如 Claude Desktop）可调用 |
| US-MCP-2 | As a 开发者, I want 连接外部 MCP Server 并自动发现其工具, so that Agent 能力可按需扩展 |
| US-MCP-3 | As a 演示者, I want 在对话中触发 MCP 工具调用并看到结果, so that 展示 MCP 协议的互操作性 |

### 2.4 Skill 技能系统

| 编号 | 用户故事 |
|------|---------|
| US-SK-1 | As a 开发者, I want 以插件形式注册 Skill 并热加载, so that 新增技能无需重启服务 |
| US-SK-2 | As a 演示者, I want 在 Skill 市场查看已注册技能并启用/禁用, so that 可控制 Agent 可用技能范围 |
| US-SK-3 | As a 开发者, I want 将多个 Skill 编排成工作流执行, so that 复杂任务可一步完成 |

### 2.5 服务端

| 编号 | 用户故事 |
|------|---------|
| US-SRV-1 | As a 开发者, I want 服务端提供统一 API 网关和 SSE 流式响应, so that 前端只需对接一个入口 |
| US-SRV-2 | As a 开发者, I want JWT + API Key 双模式认证, so that 前端用 JWT、外部系统用 API Key |
| US-SRV-3 | As a 演示者, I want 演示多租户隔离, so that 展示系统的数据隔离能力 |

### 2.6 A2UI Catalog

| 编号 | 用户故事 |
|------|---------|
| US-A2UI-1 | As a 演示者, I want Agent 返回表单卡片而非纯文本追问, so that 用户通过表单交互而非打字 |
| US-A2UI-2 | As a 开发者, I want 查看 Agent 返回的 UI schema 原文, so that 我能理解声明式 UI 的工作原理 |
| US-A2UI-3 | As a 演示者, I want 看到 Fixed Schema 和 Dynamic Schema 两种渲染模式, so that 展示 A2UI 的灵活性 |

### 2.7 前端展示层

| 编号 | 用户故事 |
|------|---------|
| US-FE-1 | As a 演示者, I want 一个统一的对话界面作为主入口, so that 演示时不用频繁切换页面 |
| US-FE-2 | As a 开发者, I want 各管理面板（知识库、Agent、Skill、MCP）布局清晰, so that 快速定位功能 |
| US-FE-3 | As a 演示者, I want 对话中内嵌 A2UI 卡片和推理链折叠面板, so that 演示信息层次分明 |

---

## 3. 需求池（P0/P1/P2 分级）

### 3.1 知识库管理（KB）

| ID | 优先级 | 需求描述 | 验收标准 |
|----|--------|---------|---------|
| KB-001 | P0 | 文档上传：支持 PDF / Markdown / TXT / DOCX 四种格式 | 上传后返回文档 ID，文件持久化存储 |
| KB-002 | P0 | 文档切片：支持按段落、固定长度两种切分策略，可配置 chunk_size 和 overlap | 切片后返回 chunk 列表，参数可调 |
| KB-003 | P0 | 向量化：调用 OpenAI 兼容 embedding 模型生成向量，存入 ChromaDB | 向量入库成功，可通过 collection 查询 |
| KB-004 | P0 | 混合检索：语义检索 + 关键词检索，支持 top-k 和 score 过滤 | 返回结果含 score 排序，可设阈值过滤 |
| KB-005 | P1 | 文档管理：文档列表、删除、重建索引 | 支持批量删除和单文档重建 |
| KB-006 | P1 | 切片预览：查看指定文档的切片列表和内容 | 管理面板可展开查看每个 chunk |
| KB-007 | P2 | 语义切片：基于 embedding 相似度的语义切分策略 | 相邻语义块相似度低于阈值时切分 |
| KB-008 | P2 | 文档元数据：支持为文档打标签、按标签筛选 | 文档列表支持标签过滤 |

### 3.2 Agent 智能体（AG）

| ID | 优先级 | 需求描述 | 验收标准 |
|----|--------|---------|---------|
| AG-001 | P0 | 多轮对话：支持上下文记忆，保留对话历史 | 第二轮对话可引用第一轮内容 |
| AG-002 | P0 | 流式输出：通过 SSE 逐 token 推送回复 | 前端打字机效果，首 token < 1s |
| AG-003 | P0 | 工具调用：Agent 可调用知识库检索、Skill 执行、MCP 工具 | 工具调用结果可见，至少支持 3 类工具 |
| AG-004 | P0 | 推理链展示：ReAct 模式（Thought → Action → Observation） | 前端可折叠展示推理过程 |
| AG-005 | P0 | Agent 配置：可配置 system prompt、工具集、模型参数（temperature 等） | 配置变更后新对话生效 |
| AG-006 | P1 | 上下文窗口管理：对话超长时自动截断或摘要 | 超过 token 限制不报错，自动处理 |
| AG-007 | P1 | 多 Agent 配置：支持创建和切换多个 Agent 配置 | Agent 配置列表可保存和切换 |
| AG-008 | P2 | Agent 记忆持久化：对话历史持久化到数据库 | 刷新页面后历史对话可恢复 |
| AG-009 | P0 | Supervisor 自主路由：按能力、风险与复杂度选择直接回答、只读工具、研究或写工作流 | 天气走 MCP；写操作走审批；普通连接词不误判 |
| AG-010 | P0 | Deep Research：快速 / 深度研究，带预算、来源、取消和恢复 | 研究报告引用可点击，重启后 interrupted 可手动恢复 |

### 3.3 MCP 协议集成（MCP）

| ID | 优先级 | 需求描述 | 验收标准 |
|----|--------|---------|---------|
| MCP-001 | P0 | MCP 客户端：连接外部 MCP Server，自动发现并调用工具 | 成功连接至少 1 个外部 MCP Server |
| MCP-002 | P0 | MCP 服务端：将知识库检索、Skill 执行暴露为 MCP 工具 | 外部客户端可连接并调用工具 |
| MCP-003 | P0 | stdio 传输：支持 stdio 传输模式 | 通过 stdio 启动 MCP Server 可被连接 |
| MCP-004 | P1 | SSE 传输：支持 SSE 传输模式 | 通过 HTTP SSE 连接 MCP Server |
| MCP-005 | P1 | MCP 配置管理：前端可配置外部 MCP Server 连接信息 | 支持添加/删除/编辑 MCP Server 配置 |
| MCP-006 | P2 | MCP 工具缓存：缓存工具发现结果，减少重复请求 | 二次连接时工具列表秒出 |
| MCP-007 | P0 | 租户 Agent 自动启用与工具风险策略 | 连接后下一轮对话生效；未知工具不进入自动执行层 |

### 3.4 Skill 技能系统（SK）

| ID | 优先级 | 需求描述 | 验收标准 |
|----|--------|---------|---------|
| SK-001 | P0 | Skill 注册：以 Python 插件形式注册，定义输入/输出 schema | 新增 Skill 文件后自动注册成功 |
| SK-002 | P0 | Skill 执行：Skill 内部可调用工具、调用 LLM、调用其他 Skill | 至少实现 2 个示例 Skill 可执行 |
| SK-003 | P0 | Skill 发现：Agent 可发现已注册的 Skill 并按需调用 | Agent 对话中可触发 Skill 执行 |
| SK-004 | P0 | Skill 市场 UI：前端展示已注册 Skill 列表、启用/禁用、详情查看 | 禁用的 Skill Agent 不可调用 |
| SK-005 | P1 | Skill 热加载：运行时加载新 Skill 无需重启服务 | 新增 Skill 文件后自动发现并注册 |
| SK-006 | P1 | Skill 编排：支持将多个 Skill 编排为简单 DAG 工作流 | 至少 1 个编排示例可执行 |
| SK-007 | P2 | Skill 版本管理：支持 Skill 多版本共存和切换 | 同名 Skill 可有 v1/v2 两个版本 |
| SK-008 | P2 | 可视化编排：前端拖拽式 Skill 工作流编辑器 | 可拖拽创建简单 DAG |

### 3.5 服务端（SRV）

| ID | 优先级 | 需求描述 | 验收标准 |
|----|--------|---------|---------|
| SRV-001 | P0 | API 网关：统一入口、路由分发、CORS 配置 | 所有 API 经统一前缀访问 |
| SRV-002 | P0 | SSE 流式响应：Agent 回复通过 SSE 推送 | 前端 EventSource 可接收流式数据 |
| SRV-003 | P0 | RESTful API：知识库、Agent、Skill、MCP 均提供 REST 接口 | Swagger 文档可查看所有接口 |
| SRV-004 | P1 | JWT 认证：登录获取 JWT，API 请求携带 Bearer Token | 未认证请求返回 401 |
| SRV-005 | P1 | API Key 认证：支持 API Key 方式认证（供外部系统调用） | API Key 请求通过认证 |
| SRV-006 | P1 | RBAC 权限：admin / user 两种角色，不同角色可访问不同 API | user 角色无法访问管理类 API |
| SRV-007 | P1 | 多租户隔离：租户级别数据隔离，知识库和会话按租户隔离 | 租户 A 看不到租户 B 的数据 |
| SRV-008 | P2 | 速率限制：API 级别 rate limiting | 超限请求返回 429 |
| SRV-009 | P2 | 审计日志：记录关键操作（文档上传、Agent 配置变更等） | 审计日志可查询 |

### 3.6 A2UI Catalog（A2UI）

| ID | 优先级 | 需求描述 | 验收标准 |
|----|--------|---------|---------|
| A2UI-001 | P0 | 组件目录定义：定义表单、卡片、列表、确认框四类基础组件 | 每类组件有 JSON schema 定义 |
| A2UI-002 | P0 | 动态渲染引擎：接收 JSON schema，按 Catalog 动态渲染对应 React 组件 | 前端可渲染任意合法 schema |
| A2UI-003 | P0 | Fixed Schema 模式：预定义组件树，Agent 填充数据 | Agent 返回带数据的固定 schema |
| A2UI-004 | P0 | Agent 返回 A2UI：Agent 可在回复中附带 A2UI 操作指令 | 对话中出现渲染后的卡片组件 |
| A2UI-005 | P1 | Dynamic Schema 模式：Agent 动态组装组件树 | Agent 根据上下文动态选择组件组合 |
| A2UI-006 | P1 | A2UI 预览页：独立页面查看 A2UI 组件渲染效果和 schema 原文 | 可选择组件类型并预览 |
| A2UI-007 | P1 | 图表组件：支持简单图表（柱状图/折线图）渲染 | Agent 可返回图表数据并渲染 |
| A2UI-008 | P2 | 自定义组件注册：支持前端注册自定义组件到 Catalog | 注册后 Agent 可引用 |
| A2UI-009 | P2 | 组件交互回调：A2UI 组件操作（如表单提交）可回传 Agent | 表单提交后 Agent 可接收并处理 |

### 3.7 前端展示层（FE）

| ID | 优先级 | 需求描述 | 验收标准 |
|----|--------|---------|---------|
| FE-001 | P0 | 对话界面：流式消息渲染、推理链折叠面板、A2UI 卡片内嵌 | 可正常多轮对话，推理链可展开/折叠 |
| FE-002 | P0 | 知识库管理面板：文档上传、切片预览、检索测试 | 可完成上传→预览→检索测试全流程 |
| FE-003 | P0 | Agent 配置页：system prompt 编辑、工具选择、模型参数配置 | 配置保存后新对话生效 |
| FE-004 | P0 | Skill 市场页：Skill 列表、启用/禁用开关、详情查看 | 禁用 Skill 后 Agent 不可调用 |
| FE-005 | P0 | A2UI 预览区：渲染 Agent 返回的 UI 组件，支持实时预览 | 对话中 A2UI 卡片正常渲染 |
| FE-006 | P1 | MCP 配置页：MCP Server 连接配置、工具列表查看 | 可添加 MCP Server 配置 |
| FE-007 | P1 | 租户管理页：租户列表、切换租户、租户配置 | 可切换租户并验证数据隔离 |
| FE-008 | P1 | 侧边导航：统一导航栏，模块间快速切换 | 所有模块入口可达 |
| FE-009 | P2 | 暗色主题：支持暗色模式切换 | 主题切换后界面正常 |
| FE-010 | P2 | 移动端适配：基本响应式布局 | 手机浏览器可基本使用 |

### 3.8 基础设施（INF）

| ID | 优先级 | 需求描述 | 验收标准 |
|----|--------|---------|---------|
| INF-001 | P0 | 项目结构：前后端分离的 monorepo 结构，清晰的目录划分 | 目录结构合理，模块边界清晰 |
| INF-002 | P0 | 环境配置：.env 配置文件，含 LLM API Key、ChromaDB 路径等 | .env.example 提供完整模板 |
| INF-003 | P0 | 启动脚本：一键启动后端 + 前端 + ChromaDB | 执行脚本后所有服务可用 |
| INF-004 | P0 | Seed 数据：示例文档、示例 Skill、示例 Agent 配置 | 首次启动有预置数据可演示 |
| INF-005 | P1 | API 文档：Swagger/OpenAPI 自动生成 | /docs 可查看交互式 API 文档 |
| INF-006 | P1 | README：项目说明、架构图、快速启动指南 | 新人按 README 可独立启动 |
| INF-007 | P2 | Docker 部署：Dockerfile + docker-compose | docker compose up 一键启动 |
| INF-008 | P2 | CI 流水线：GitHub Actions 基本检查 | PR 触发 lint + 基础测试 |

### 3.9 需求优先级汇总

| 优先级 | 数量 | 说明 |
|--------|------|------|
| P0 | 25 | Demo 核心链路，缺一不可 |
| P1 | 19 | 重要增强，时间允许即做 |
| P2 | 14 | 锦上添花，Demo 阶段可省略 |

---

## 4. 各模块功能边界

### 4.1 模块功能边界定义

| 模块 | 输入 | 核心能力 | 输出 | 不做什么 |
|------|------|---------|------|---------|
| 知识库管理 | 文档文件（PDF/MD/TXT/DOCX）、检索查询 | 文档解析、切片、向量化、混合检索 | chunk 列表、检索结果（含 score） | 不做 OCR；不做表格结构化提取；不做跨知识库联合检索 |
| Agent 智能体 | 用户消息、Agent 配置、工具集 | 意图理解、工具调用决策、ReAct 推理、流式回复 | 文本回复、工具调用记录、A2UI 操作指令、推理链 | 不做多 Agent 协作（P2）；不做 Agent 自主创建工具；不做复杂 Flow 编排（v1 的 Flow 引擎不属于 v2 范围） |
| MCP 协议集成 | MCP Server 连接配置、工具调用请求 | MCP 客户端连接/工具发现/工具调用、MCP 服务端工具暴露 | 工具列表、工具调用结果 | 不做 MCP 协议的非标准扩展；不做 MCP Server 的权限管理 |
| Skill 技能系统 | Skill 插件文件、执行参数、编排定义 | Skill 注册/发现/执行/编排 | Skill 执行结果 | 不做 Skill 的可视化编排（P2）；不做 Skill 市场（在线分发）；不做 Skill 沙箱隔离 |
| 服务端 | HTTP 请求、SSE 连接 | API 网关、认证鉴权、流式响应、多租户隔离 | RESTful JSON 响应、SSE 流 | 不做微服务拆分；不做消息队列；不做分布式部署 |
| A2UI Catalog | Agent 返回的 JSON schema | 组件定义管理、schema 解析、动态渲染 | 渲染后的 React 组件 | 不做组件主题定制（P2）；不做组件市场（在线分发）；不做完整的低代码搭建能力 |
| 前端展示层 | 用户交互、后端 API 响应 | 对话交互、管理面板、A2UI 渲染、状态管理 | 用户可见的 UI 界面 | 不做 SSR；不做 PWA；不做完整的权限管理 UI（仅基础 RBAC 展示） |

### 4.2 模块间数据流

```
用户
  |
  v
前端展示层 ──── HTTP/SSE ─────> 服务端（API 网关 + 认证）
                                  |
                                  v
                              Agent 智能体
                              /    |    \
                             v     v     v
                    知识库管理  Skill 系统  MCP 客户端
                        |         |           |
                        v         v           v
                    ChromaDB   工具/LLM    外部 MCP Server
                        |         |           |
                        |         v           |
                        |     MCP 服务端 <----+
                        |    (暴露 KB检索
                        |     和 Skill 执行)
                        v
                    A2UI Catalog
                    (Agent 返回 schema
                     前端按 Catalog 渲染)
                        |
                        v
                    前端展示层 (渲染 A2UI 组件)
```

### 4.3 关键数据流说明

| 数据流 | 说明 |
|--------|------|
| 前端 → 服务端 → Agent | 用户消息经 API 网关路由到 Agent，SSE 建立流式通道 |
| Agent → 知识库 | Agent 调用知识库检索工具，传入 query，获取 chunks + score |
| Agent → Skill | Agent 发现并调用已注册 Skill，传入参数，获取执行结果 |
| Agent → MCP 客户端 → 外部 MCP Server | Agent 通过 MCP 客户端调用外部工具 |
| MCP 服务端 ← 外部客户端 | 外部 MCP 客户端连接本系统 MCP Server，调用知识库检索/Skill 执行工具 |
| Agent → A2UI → 前端 | Agent 返回 A2UI schema，经 SSE 推送到前端，前端按 Catalog 渲染 |
| 前端 → 知识库管理面板 → 服务端 → ChromaDB | 前端上传文档，服务端解析切片向量化，存入 ChromaDB |

---

## 5. 待确认问题

| 编号 | 问题 | 影响范围 | 建议方向 |
|------|------|---------|---------|
| Q-1 | embedding 模型默认用哪家？OpenAI text-embedding-3-small 还是本地模型（如 bge-small-zh）？ | 知识库管理 | 建议默认 OpenAI 兼容接口，配置可切换；如需离线演示则预置本地模型选项 |
| Q-2 | 多租户的"租户"在 Demo 中如何体现？是预置 2 个租户演示隔离，还是支持动态创建？ | 服务端、前端 | 建议预置 2 个租户（tenant-a / tenant-b），演示切换即可，不做动态创建 |
| Q-3 | RBAC 的角色权限粒度到什么程度？仅区分 admin/user 能否满足演示？ | 服务端 | 建议 Demo 阶段仅 admin/user 两级，admin 可管理配置，user 仅可对话 |
| Q-4 | MCP Server 暴露哪些工具？仅知识库检索，还是也暴露 Skill 执行？ | MCP 协议集成 | 建议暴露知识库检索 + 1-2 个示例 Skill，展示 MCP 的工具暴露能力 |
| Q-5 | Skill 编排的 DAG 复杂度？Demo 阶段是否需要条件分支、循环等？ | Skill 技能系统 | 建议 Demo 阶段仅支持线性 DAG（A → B → C），不支持条件分支和循环 |
| Q-6 | A2UI 组件的交互回调（如表单提交）是否需要回传 Agent？还是仅前端展示？ | A2UI Catalog | 建议 P0 阶段仅展示（Agent 返回卡片，用户查看），P1 再加交互回调 |
| Q-7 | 前端是否需要登录页？还是 Demo 阶段默认已登录直接进入？ | 前端展示层 | 建议有简单登录页（输入用户名/密码），演示认证流程完整性 |
| Q-8 | 对话历史是否需要持久化？还是 Demo 阶段仅内存存储？ | Agent 智能体 | 建议 P0 内存存储即可，P1 加数据库持久化 |
| Q-9 | ChromaDB 用 Docker 运行还是 Python 嵌入式模式？ | 基础设施 | 建议嵌入式模式（chromadb 库直接调用），减少启动依赖，简化 Demo 环境 |
| Q-10 | 是否需要预置一个完整的外部 MCP Server 示例供连接演示？ | MCP 协议集成 | 建议预置一个简单的 MCP Server 示例（如天气查询），方便演示 MCP 客户端连接 |

---

## 6. 演示场景设计

### 6.1 场景一：知识库问答全链路

**目标**：展示知识库管理 → Agent 推理 → 前端渲染的核心链路。

| 步骤 | 操作 | 涉及模块 | 展示要点 |
|------|------|---------|---------|
| 1 | 在知识库管理面板上传一份 PDF 文档 | 知识库管理、前端 | 文档上传后自动切片、向量化，展示 chunk 列表 |
| 2 | 在检索测试框输入问题，查看检索结果 | 知识库管理 | 展示混合检索结果，score 排序 |
| 3 | 切换到对话界面，提出与文档相关的问题 | Agent、前端 | Agent 流式输出回答 |
| 4 | 展开推理链折叠面板 | Agent、前端 | 展示 Thought → Action(kb_retrieval) → Observation 推理过程 |
| 5 | 查看回答中的来源引用 | Agent、知识库管理 | 回答标注引用了哪些 chunk |

**串联模块**：知识库管理 + Agent + 服务端(SSE) + 前端

### 6.2 场景二：Skill 编排与 A2UI 卡片渲染

**目标**：展示 Skill 系统的注册/发现/执行能力和 A2UI 声明式 UI 渲染。

| 步骤 | 操作 | 涉及模块 | 展示要点 |
|------|------|---------|---------|
| 1 | 在 Skill 市场查看已注册的 Skill 列表 | Skill 系统、前端 | 展示 Skill 名称、描述、状态（启用/禁用） |
| 2 | 启用"数据分析"Skill，查看详情 | Skill 系统、前端 | 展示 Skill 的输入/输出 schema |
| 3 | 在对话界面请 Agent 执行数据分析任务 | Agent、Skill 系统 | Agent 发现并调用 Skill，展示推理链 |
| 4 | Agent 返回 A2UI 卡片（如数据表格 + 图表） | Agent、A2UI Catalog | 对话中出现渲染后的表格和图表组件，非纯文本 |
| 5 | 切换到 A2UI 预览页查看 schema 原文 | A2UI Catalog、前端 | 展示声明式 UI 的 JSON schema 和渲染效果对照 |

**串联模块**：Skill 系统 + Agent + A2UI Catalog + 前端

### 6.3 场景三：MCP 协议互操作

**目标**：展示 MCP 客户端连接外部 Server 调用工具，以及本系统 MCP Server 被外部调用。

| 步骤 | 操作 | 涉及模块 | 展示要点 |
|------|------|---------|---------|
| 1 | 在 MCP 配置页添加外部 MCP Server 连接 | MCP 协议集成、前端 | 配置连接信息后自动发现工具列表 |
| 2 | 在对话界面提出需要外部工具的问题 | Agent、MCP 协议集成 | Agent 通过 MCP 客户端调用外部工具，展示推理链 |
| 3 | 在终端启动本系统的 MCP Server（stdio 模式） | MCP 协议集成 | 展示 MCP Server 启动日志和暴露的工具列表 |
| 4 | 用 MCP 客户端（如 Claude Desktop 或脚本）连接本系统 MCP Server | MCP 协议集成 | 调用知识库检索工具，返回检索结果 |
| 5 | 展示 MCP Server 暴露的 Skill 执行工具 | MCP 协议集成、Skill 系统 | 外部客户端调用 Skill 执行工具并获取结果 |

**串联模块**：MCP 协议集成 + Agent + 知识库管理 + Skill 系统 + 服务端 + 前端

---

## 附录：技术栈确认

| 层 | 技术选型 | 说明 |
|----|---------|------|
| 后端 | Python 3.11+ / FastAPI | AI 生态最成熟，LangChain/LlamaIndex/MCP SDK 官方支持 |
| 前端 | React 19 / Next.js 15 / TypeScript / assistant-ui / Zustand | AI SDK UIMessage 流，组件与状态持久化 |
| 向量存储 | ChromaDB | 轻量本地部署，适合 Demo |
| LLM 接入 | OpenAI 兼容接口 | 可接 OpenAI / DeepSeek / Qwen 等任意兼容模型 |
| Agent 框架 | LangChain / LangGraph | Supervisor、工具调用与持久化工作流 |
| MCP SDK | mcp 官方 Python SDK | 本轮仅交付 stdio |
| 仓库位置 | /Users/wyf/workspace/aicoding/guanxin-v2 | 独立仓库，与 guanxin-sdk 同级 |

---

## v0.2.0-demo 交付与延期矩阵

上述需求池保留产品规划含义，不代表每一项均已交付。本轮以此矩阵及 [验收报告](releases/v0.2.0-demo-acceptance.md) 为准。

| 范围 | 本轮交付 | 延期或边界 |
|---|---|---|
| 知识库 | PDF 文本层、DOCX、TXT/Markdown 上传，切片预览，向量 top-k，租户隔离，删除 | OCR、混合关键词检索、score 阈值、标签、批量删除/重建及语义切片延期 |
| Agent | Supervisor、只读工具循环、会话历史、租户级配置、Quick/Deep Research | 不承诺首 token <1s；多 Agent 切换与高级上下文管理延期 |
| MCP | 外部天气客户端；对外知识检索、文本摘要、数据分析三个固定只读工具 | 不开放通用 Skill 执行器；远程 SSE/HTTP MCP 延期 |
| Skill/工作流 | 内置技能、最多 16 步线性流程、补参、审批、恢复与幂等执行 | 热加载、多版本、条件分支、并行 DAG、拖拽编排延期 |
| 服务端 | JWT/API Key、RBAC、SQLite/checkpoint、Chroma | users JSON 是管理型 Demo 数据；登录账号与 Key 仍为进程内预设数据，账号数据库迁移延期 |
| A2UI/前端 | React 19/Next.js 15；五类卡片、图表、Schema 预览、导航、暗色主题 | 通用组件回调和自定义组件市场延期；工作流交互有专用协议 |
| 基础设施 | 启动脚本、隔离测试、全量 CI、操作手册与发布材料 | 生产部署、Docker 交付、审计日志和限流延期 |

只有全部自动化门禁、真实七组场景和远端 main CI 通过后，状态才可改为“v0.2.0-demo 已验收”，并创建发布标签。
