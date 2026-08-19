# 观心 v2 稳定演示版设计规格

## 1. 目标与边界

本轮将现有功能原型收口为可重复演示的稳定版本：服务重启后文档、对话和 Agent 配置不丢失；Assistant 使用真实登录身份和租户；历史消息能完整恢复文本、推理、工具调用、审批和 A2UI；核心管理动作执行服务端 RBAC。

本轮不包含生产部署、审计日志、限流、LangGraph interrupt/resume、远程 MCP SSE 或用户账户 SQLite 迁移。用户继续由 `backend/data/users.json` 管理。AI SDK 是目标聊天协议；旧 AG-UI 和自定义 SSE 仅保留到新链路验收完成。

## 2. 数据与持久化设计

### 2.1 SQLite 基础设施

- 新增 `DATABASE_PATH`，默认 `./data/guanxin.db`。
- 使用 Python 标准库 `sqlite3`，每次仓储操作创建独立连接。
- 每个连接启用 `PRAGMA journal_mode=WAL`、`PRAGMA foreign_keys=ON` 和 `PRAGMA busy_timeout=5000`。
- 启动时执行版本化、幂等 schema 初始化；`schema_version` 记录当前版本。
- 保留现有 Store/Service 方法形态，以 SQLite 仓储替换内存字典，避免 API 与 Agent 层大面积改写。

### 2.2 表结构

- `documents`：文档标识、租户、文件信息、处理状态、chunk 数量、错误、JSON metadata、时间戳。
- `document_chunks`：chunk 标识、文档外键、租户、正文、顺序、JSON metadata；文档删除时级联删除。
- `conversations`：对话标识、租户、用户、Agent、标题、时间戳。
- `conversation_messages`：稳定 message ID、对话外键、角色、文本、推理、JSON 工具调用、JSON A2UI、标准 UI parts、时间戳。
- `agent_configs`：以 `(tenant_id, agent_id)` 唯一，保存模型、提示词、temperature、max tokens、工具、Skill 和 MCP 选择。
- `tool_approvals`：approval ID、tool call ID、对话、动作快照、状态和时间戳；状态为 pending/approved/rejected/consumed。

### 2.3 一致性规则

- 上传流程固定为：创建数据库记录 → 保存文件 → 解析/切片 → 写入 Chroma → 标记 READY。
- 失败必须标记 FAILED；若 Chroma 已部分写入，则按 doc ID 补偿删除。
- 删除前验证租户归属；Chroma 删除失败时中止。随后删除文件与 SQLite 元数据，文件缺失只记告警。
- 种子数据只在记录不存在时写入，重启不得覆盖管理员修改或重复上传示例文档。

## 3. Assistant 与消息协议

### 3.1 身份与会话

- AI SDK Transport 动态读取 access token 并发送 Bearer 头；无 token 时不发起聊天请求。
- `/api/agent/chat/aisdk` 强制使用 JWT/API Key 认证，租户和用户完全来自认证上下文，不允许 default/anonymous 回退。
- AI SDK 请求 `id` 必须是通过会话 REST API 创建的 conversation UUID，并属于当前租户和用户；不存在或跨租户统一返回 404。
- Assistant 页面提供固定宽度会话侧栏，移动端使用抽屉，支持新建、切换、删除和按更新时间排序。
- 刷新后恢复最近会话；切换会话时重新初始化 `useChat`，加载完整标准 UI parts。

### 3.2 消息与工具事件

- 内部工具调用和结果共享稳定 `tool_call_id`，A2UI 也通过该 ID 关联。
- 一条助手消息在流结束时一次性持久化，包含文本、reasoning、tool calls、approval 和 A2UI。
- 历史详情继续返回旧字段，并新增 `message_id` 与标准 `parts`，保证前端完整恢复且兼容管理 API。
- A2UI 使用带类型的 `data-a2ui` UIMessage data part，由 assistant-ui Data Renderer 直接渲染，不再使用临时 Context 聚合。

### 3.3 审批幂等

- 确认卡片只提交 AI SDK approval response，不再额外发送“确认操作”文本。
- useChat 使用 `lastAssistantMessageIsCompleteWithApprovalResponses` 自动续发。
- approval 状态写入 SQLite；批准后在事务中原子切换为 consumed，再执行动作。同一 approval ID 的重复提交不得重复执行。

## 4. Agent 配置与权限

### 4.1 Agent 配置

- `GET /api/agent/config` 返回当前租户持久化默认 Agent 配置及可用模型、工具、Skill、MCP 列表。
- `PUT /api/agent/config` 仅 admin 可用，支持模型、temperature、max tokens、system prompt 和能力选择。
- 模型必须位于可用列表，temperature 为 0–2，max tokens 为 1–32768，能力名称必须存在。
- Agent 执行只读取持久化配置；旧聊天请求中的运行时覆盖字段保留解析但忽略并标记弃用。
- admin 可在页面编辑并保存；普通用户看到同一页面的只读状态。

### 4.2 平衡 RBAC

- 所有登录用户：知识库上传/查询/删除、文本摘要、数据分析、读取 Agent 配置、使用已连接的 MCP 工具。
- 仅 admin：修改 Agent 配置、MCP 注册/删除/连接、用户查询/增删改、数据导出、系统诊断。
- 权限同时在 API、SkillExecutor 和 Agent 工具注册/执行层生效；普通用户既不能发现也不能绕过前端调用管理工具。
- `SkillContext` 增加 `user_role`，作为 Skill 层权限依据。

## 5. A2UI 与前端呈现

- Preview 契约统一为 `{ "schema": A2UISchema }`。
- 工具渲染固定映射：知识库使用 Sources/List；数据分析使用 Chart；其他 Skill/MCP 使用 Tool；确认操作使用 Confirmation；未知工具使用通用 Tool。
- 会话历史必须恢复同样的组件状态，不允许刷新后退化为纯文本。
- Agent 配置表单提供保存、取消和服务器值恢复；普通用户所有控件只读。

## 6. 数据重置与迁移

- 实施时保留 `backend/data/users.json`。
- 旧 uploads、Chroma 和业务数据库不迁移；只有在用户再次确认准确路径和不可恢复影响后才执行清空。
- 清空后通过启动生命周期重建干净的示例文档、默认 Agent 配置和天气 MCP 配置。

## 7. 验收与退出条件

- 后端覆盖 SQLite 幂等初始化、重启持久、外键、事务、租户隔离、RBAC、A2UI 契约和 approval 幂等。
- 前端 typecheck、production build、ESLint 全绿。
- Playwright 覆盖：上传后问答、Skill 图表、MCP 调用、审批单次执行、跨租户隔离、刷新后完整历史恢复。
- 自动测试 mock LLM/Embedding，不调用付费模型；发布前仅做一次人工 live smoke test。
- 新链路全部验收通过后删除 AG-UI、自定义旧 SSE、过期注释和未使用适配代码，AI SDK 成为唯一聊天协议。

## 8. 实施顺序

1. 建立 Git 基线和忽略规则。
2. 实现 SQLite 基础设施与三类 Store。
3. 接通 Assistant 认证、真实 conversation ID 和历史恢复。
4. 完成工具事件、A2UI 与 approval 幂等。
5. 完成 Agent 配置、RBAC 和前端编辑体验。
6. 完成 lint、文档、Playwright 和旧链路清理。

