---
id: workflows
type: module-design
title: 持久化工作流引擎
status: draft
parent: architecture
depends-on:
  - platform-core
  - tool-authorization
---

# 持久化工作流引擎

## 职责

承接所有会改变业务数据的操作：把 Agent 的写意图变成一份可审阅的线性计划，落库后由 LangGraph 逐步执行，在人需要介入处暂停，在进程异常处停下来交给人判断。

## 边界

- **唯一的写操作通道**：通用 Agent 只能通过 `request_business_workflow` 进入本模块，任何模块都不得给 Agent 直接写工具。
- 只支持线性计划，不做条件分支、并行 DAG 或跨机执行。
- 不实现工具本身：工具定义来自 `tool-authorization` 的过滤结果，执行体是 Skill / MCP / 知识库写入。
- 业务状态以 `workflow_runs` / `workflow_steps` / `workflow_interrupts` 为准，checkpoint 只保存执行游标。

## 契约

**规划**：Planner 只看到当前租户已启用且经 RBAC 过滤的工具，产出最多 16 步、含 `$inputs.*` / `$steps.*` 引用的计划；服务端校验工具名、参数与引用，失败只允许模型自修一次。

**状态机**：`planning → running → {waiting_input | waiting_approval} → running → completed | failed | cancelled`；风险工具窗口内进程退出则置 `uncertain`，仅 admin 可 `retry` / `mark_completed` / `cancel`，绝不自动重放。

**人工介入**：`workflow_interrupts`（input / approval / recovery）承载暂停点；`POST /api/agent/workflows/{run_id}/respond` 先在业务表校验 interrupt 归属与工具当前是否仍被授权（403），再以同一 interrupt 幂等恢复；被撤销权限的恢复请求不会触达工具。

**幂等执行**：每次调用前写 `executing` 与幂等键（`workflow_step_executions` 唯一约束），重复恢复直接返回已保存结果。只读工具失败自动重试一次；写操作与 MCP 不重试。

**并发与清理**：部分唯一索引保证每个会话至多一个活动流程；新请求遇到活动流程返回 409；删除会话级联删除工作流记录与 checkpoint thread。

**呈现**：`workflow_public_data` 是唯一对前端输出的形状（步骤、当前中断、表单字段、结果），前端只负责显示与回传，不解释状态机。

## 已知限制

- 计划无法中途修改：只能继续或取消。
- 恢复依赖单进程内的 LangGraph 图缓存，重启后按业务记录重建。
- 旧 `tool_approvals` 记录仅作历史展示，不参与新流程。
