---
id: agent-runtime
type: module-design
title: Agent 执行内核
status: draft
parent: architecture
depends-on:
  - platform-core
  - tool-authorization
  - workflows
---

# Agent 执行内核

## 职责

把「一条用户消息」变成一次可恢复的 Deep Agents 运行，并把官方原生事件投递成可断线重放的协议流，同时把业务（工作流、研究额度、虚拟文件）投影回线程状态。

## 边界

- **不实现模型 / 工具循环**：循环、消息组装、状态机、虚拟文件系统都来自 Deep Agents 与 LangGraph 官方实现；本模块只做配置、策略中间件、事件 envelope 适配与业务投影。
- **不直接执行业务写操作**：需要改动业务数据时只能调用 `request_business_workflow` 移交 `workflows`。
- 不接触宿主文件系统：`StateBackend` 是 checkpoint 支撑的虚拟工作区。
- 不信任客户端提交的 tenant / user / model / 工具权限，也不接受除 `run.start` 以外的协议命令。

## 契约

**线程与身份**：`conversation_id` 由服务端创建，对应唯一 LangGraph 线程 `agent:{conversation_id}`；每次读写都按 tenant_id + user_id 校验归属，越权 404。

**输入**：一条 human 文本（非空、≤100000 字符、客户端可带 id）加可选 `research_mode ∈ {auto, quick, deep}`。历史消息只作为文本上下文导入一次，**不重放历史工具调用**。

**run 生命周期**：run 准入写入 `agent_runs`（`(conversation_id, request_key)` 唯一、部分唯一索引保证单会话至多一个 running）。运行在后台任务中执行；关闭订阅不取消任务，显式 `cancel` 才取消并落库为 `cancelled`；服务重启把遗留 running 标为 `interrupted` 且不自动重放。

**事件**：官方 v3 事件只做三件事——消息事件的 tuple → `data`/`node` 适配、写入带自增 `seq` 的 `agent_events`、业务投影（`workflow`、`run_status`、`research_review`、文件列表）附加到 `values`。`/stream/events` 从 `since` 游标重放并保活心跳。

**资源上限**：单次运行模型 16 次、工具 24 次、480 秒；超限以显式错误结束，不返回伪造结果。

**状态唯一性**：checkpoint 是执行状态；`conversation_messages` 只是兼容历史与导出的投影，导入时与 checkpoint 消息按 id 对齐并保持顺序。

**取消与恢复时机**：允许「接受用户消息但 checkpoint 尚未写入」的中断——恢复时把缺失的用户消息补进图输入。

## 已知限制

- 单进程调度：同一会话的并发提交被拒（409），跨会话共享一个事件循环与一个 SQLite 写者。
- 不支持 checkpoint 时间旅行与分支编辑，`/history` 恒返回空数组。
- 会话附件只接收文本，图片 / PDF 附件未迁移。
- 遗留 transcript 与 checkpoint 的合并逻辑刻意保留，删除会影响已有会话历史。
