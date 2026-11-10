---
id: research
type: module-design
title: 联网研究与引用审查
status: draft
parent: architecture
depends-on:
  - platform-core
---

# 联网研究与引用审查

## 职责

让 Agent 能用真实网页完成研究，同时保证三件事可核查：搜索花了多少、原文到底写了什么、哪句话取自哪段原文。

## 边界

- **没有自研研究循环**：不实现 planner / gap analyzer / synthesizer，研究由 Deep Agents 调用 `web_search`、`read_source`、`record_citation` 三个只读工具完成。
- 只读：研究链路永远不注册 write 或 unknown 工具，也不访问需要登录态的网页。
- 网页正文一律视为不可信数据；本模块不判断主张是否成立。

## 契约

**预算账本**（按会话持久化，`research_ledgers`）：auto / quick 最多 2 次搜索请求与 20 个服务端动作，deep 最多 4 次请求与 40 个动作。首次搜索固定预算，取消、继续、重启或切换模式都不重置；请求串行准入（`pending`）防止并行绕过；失败且用量未知时置 `uncertain` 并暂停后续搜索；已消耗的请求不退费。动作阈值只能阻止后续请求，无法截断供应商当前请求内部的动作，因此不是费用上限。

**原文读取**（`read_source`）：仅接受本会话搜索结果中出现过的 URL、HTTPS、域名在 `RESEARCH_SOURCE_HOSTS` 白名单内、无凭据与自定义端口、解析结果为公网地址；重定向逐跳校验（最多 4 跳），正文上限 1 MB、总读取期限 25 秒，只接受 html / text / markdown。取得的正文按会话首次获取结果固化（含 `sha256`、`fetched_at`、`final_url`），不刷新、不覆盖。

**引用比对**（`record_citation`）：主张 1–2000 字符，摘录 20–4000 字符；可用 `passage_id` 引用正文的稳定片段以避免抄写偏差。只有当摘录逐字出现在已获取正文中才保存成功，返回 `quote_match: true` 与 `entailment: requires_human_review`——文字匹配不等于语义支持，人工审查状态由模型之外决定。

**旧记录兼容**：`research_runs` 等旧表保留历史读取、取消，以及「转入新的原生任务」的幂等恢复；旧报告与来源作为不可信上下文重新核实，不承诺重放旧执行状态。

## 已知限制

- 白名单由管理员配置，配置不当会直接挡住可读来源；本模块不能作为任意 URL 的通用代理。
- 付费搜索与真实模型评估不进 CI。
- 引用审查没有自动刷新或语义批准入口。
