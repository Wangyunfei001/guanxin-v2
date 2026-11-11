---
id: tool-authorization
type: module-design
title: 工具授权目录
status: draft
parent: architecture
depends-on:
  - platform-core
  - skills
  - mcp
---

# 工具授权目录

## 职责

回答一个运行时问题：**此刻这位用户、这个租户、这段会话，能调用哪些工具，各自按什么风险处置？** 知识库检索、Skill、MCP 工具与搜索工具都经由它投影成 Agent 可见的工具。

## 边界

- 不实现任何工具本身：执行体在 `skills`、`knowledge`、`mcp`、`research` 模块。
- 不做跨请求的授权缓存：每次构造都重新读取租户 Agent 配置与 MCP 政策；Agent 每次工具调用前再由中间件重建一次（MCP 探测关闭）。
- 不负责规划或执行工作流：它只向 `workflows` 提供同一套过滤后的工具定义。

## 契约

**唯一判定**：可见性与风险等级只有一份实现——`app.agent.tool_catalog.discover_tool_specs`。Agent 目录与工作流目录都从它派生，因此 MCP 禁用开关与风险分级不可能在两条路径上漂移。`kb_retrieval` 是唯一例外：两端参数契约本就不同（Agent 用工具签名，工作流额外暴露 `top_k`），各自构造。

**目录项**：每个工具带 `source_type`（builtin / skill / mcp / provider）、`effect`（read / write / unknown）、`approval_required`、`enabled`，以及由技能参数或 MCP inputSchema 推导出的结构化入参模型（工具名形如 `skill__query_users`、`mcp__weather__get_weather`）。

**Skill 的 effect 必须显式声明**：`SkillMetadata.effect` 是必填字段，无默认值，取值限于 `read` / `write` / `unknown`；注册时校验，非法值拒绝注册并记日志。风险判定 **fail-closed**——只有显式声明为 `read` 的工具才能免审批自动执行，`write` 与 `unknown` 一律进入可审批的持久化工作流。

**风险处置**：

| 条目 | 通用 Agent 可自动执行 | 进入工作流 |
|---|---|---|
| read 且非审批 | ✓ | ✓ |
| write / unknown | ✗ | ✓ |
| 未在目录中 | ✗ | ✗ |

**三层一致授权**：API dependency（路由级角色）、`SkillExecutor`（`ADMIN_ONLY_SKILLS` 拒绝普通用户）、Agent 中间件与工作流规划/执行/恢复前重过滤——任一层拒绝即不执行。

**MCP 禁用开关在两条路径上都生效**：租户策略中 `enabled = false` 的工具既不出现在 Agent 目录，也不出现在工作流目录；工作流执行时再查一次策略，目录构建之后被禁用的工具也不能执行。

**写操作的唯一入口**：写业务数据只能由 Agent 调用 `request_business_workflow` 移交 `workflows`。Agent 运行循环中没有正则旁路——问句（“如何删除用户”）得到的是解释性回答，不是变更审批卡。

**永久禁用的官方能力**：`task`（子代理）与 `execute`（宿主 shell）在模型请求与工具调用两侧都被剔除，绝不进入目录。

**虚拟文件白名单**：`ls` / `read_file` / `write_file` / `edit_file` / `delete` / `glob` / `grep` / `write_todos` / `request_business_workflow` 由 Deep Agents 自带，不触达业务数据，因此不参与目录复核。

## 已知限制

- MCP 工具的 `effect` 默认 `unknown`，需管理员在 MCP 页标注后才可能被视为只读；未标注的工具不能自动执行。
- 工具发现依赖运行时 MCP 连接状态，连接失败时对应工具从目录消失而不是报错。
- Skill 注册时的 effect 校验只保证取值合法，不校验它与 Skill 实际行为是否一致——这依赖编写 Skill 时如实声明。
