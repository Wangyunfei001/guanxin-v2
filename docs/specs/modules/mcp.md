---
id: mcp
type: module-design
title: MCP 双向集成
status: draft
parent: architecture
depends-on:
  - platform-core
  - tool-authorization
---

# MCP 双向集成

## 职责

两个方向各司其职：让观心 Agent **消费**外部 MCP Server（当前为真实天气），同时把观心自己**暴露**成一个只读 MCP 网关供外部客户端调用。

## 边界

- **网关是 HTTP API 的薄适配层**：它不直接访问 SQLite、ChromaDB 或 Skill 内部实现，不提供通用 Skill 执行器，也不提供任何写操作。
- 连接只支持本地 stdio，不做远程 SSE / 云端 MCP，不做多进程池。
- MCP 工具默认风险为 `unknown`，是否可自动执行由 `tool-authorization` 政策决定，本模块不自行放行。

## 契约

**客户端（观心 → 外部 Server）**：`connect(server, command, args, env)` 启动 stdio 子进程、initialize 并缓存工具清单与运行时状态；连接与「当前租户 Agent 已启用」是两个独立状态，管理员连接成功后本模块负责把该 Server 幂等写进租户 Agent 配置。工具以 `mcp__{server}__{tool}` 命名并按其 inputSchema 生成结构化入参。

**风险标注**：`mcp_tool_policies` 按租户 + Server + 工具记录 `enabled`、`effect`、`approval_required`；未标注即保守处理。

**网关（外部 → 观心）**：独立 stdio Server，用 `GUANXIN_API_BASE_URL` 与 `GUANXIN_API_KEY` 调用 HTTP API，API Key 绑定用户与租户。只暴露三个固定只读工具：`knowledge_retrieve(query, top_k=5)`、`text_summary(text, max_sentences=3)`、`data_analysis(data, analysis_type="basic")`，`top_k` / `max_sentences` 取值 1–20。知识结果以 `{"results": [...]}` 包装。缺密钥即启动失败；401/403、网络错误、超时与业务失败统一返回 MCP tool error，错误信息脱敏，诊断只写 stderr，stdout 专供协议。

**天气 Server（观心 → Open-Meteo）**：地理编码 + 当前天气，按位置时区返回当地时间，不引入 API Key 与新供应商抽象；工具名与输入契约保持稳定，失败返回安全错误。

## 已知限制

- 预设 API Key 是进程内数据，后端重启后需重新获取。
- 网关与天气 Server 都依赖公网或后端可用性，不提供 SLA、预警或重试编排。
