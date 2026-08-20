# 观心 v2 Agent 架构升级增量 PRD

> 版本：v2.0
> 日期：2026-08-20
> 状态：Persistent Workflow 已实施
> 作者：产品经理 许清楚

---

## 0. 文档说明

### 0.0 2026-08-20 实施更新

UP-101 已交付并扩展为统一工作流引擎：多步骤与单步写操作都支持持久化计划、动态参数表单、AI SDK 审批、LangGraph interrupt/resume、刷新/后端重启恢复、幂等执行及风险步骤 `uncertain` 人工接管。Planner 最多生成 16 个线性步骤；当前不包含分支、并行 DAG、分布式锁或远程 MCP SSE。

UP-202 的核心权限边界已前移到规划工具目录，并在执行和恢复前再次校验。UP-203 已实现最大步数与故障状态持久化，但“自动超时和草稿续作”仍为后续项。

### 0.1 文档定位

本文档是 **guanxin-v2 现有 Agent 架构的增量升级 PRD**，描述从当前"纯 ReAct 模式"升级到"U2A2S 自定义 StateGraph"的需求变更。

**与现有 PRD 的关系**：本文档是 `guanxin-v2/docs/prd.md`（v2 全功能 Demo PRD）的增量补充。原 PRD 定义的是"Demo 阶段"的 Agent 能力（对标 AG-001 到 AG-008），本次升级将其从 `langgraph.prebuilt.create_react_agent` 的简单封装，升级为具有意图分类、模式决策、Flow 编排能力的自定义 StateGraph。

### 0.2 与 guanxin-sdk U2A2S 设计的关系

本次升级是 guanxin-v2 向 U2A2S 架构对齐的第一步。guanxin-sdk 侧已产出的设计文档为 Agent 端提供了完整的技术方案：

| 文档 | 与本次升级的关系 |
|------|-----------------|
| `guanxin-sdk/docs/u2a2s/03-tech-design-agent.md` | **上游设计依据**：本次升级的 IntentParser、ModeDecision、FlowLauncher 节点均源自此文档的设计。但 v2 阶段不做 Flow 引擎（Flow 引擎属服务端能力，不在 v2 Demo 范围），FlowLauncher 在此阶段简化为"多步流程的 ReAct 子 Agent"。 |
| `guanxin-sdk/docs/u2a2s/01-product-planning.md` | 定义 U2A2S 的四模式交互和业务目标，本次升级重点实现"模式决策"适配这些模式。 |
| `guanxin-v2/docs/prd.md` 第 3.2 节 | 定义 AG-001 到 AG-008 共 8 项 Demo 需求，本次升级是 AG-001 到 AG-005 的架构升级。 |

---

## 1. 问题诊断

### 1.1 症状

用户输入 **"新增租户"** 到 Agent 对话界面，预期 Agent 应识别这是一个**操作类意图**，但实际行为是：Agent 只调用了 `kb_retrieval` 检索知识库，没有做任何租户管理相关操作。

### 1.2 根因分析（5 个 Why）

| 层级 | 分析 |
|------|------|
| **Why 1：为什么 Agent 只调了 kb_retrieval？** | System Prompt 中写了"当需要查找信息时，优先使用 kb_retrieval 工具检索知识库"。LLM 看到"新增租户"中的"租户"一词，触发了"查找信息"的判断 → 走 kb_retrieval。 |
| **Why 2：为什么 System Prompt 能带偏 LLM？** | 没有意图分类层。LLM 一次调用完成"判断意图 + 选择工具 + 生成回复"，当 System Prompt 暗示某类操作时，LLM 会优先走那条路。 |
| **Why 3：为什么需要意图分类？** | "新增租户"是 Create 操作，"查租户"是 Query 操作，"聊聊租户"是 Chat。这三个意图需要的工具链完全不同，但当前 Agent 对它们一视同仁。 |
| **Why 4：即使识别了意图，Agent 有能力执行吗？** | 没有。当前 Agent 只有 `kb_retrieval` 和 `skill_execute` 两个工具，没有租户管理的 Skill、API 工具或 MCP 工具。即使 LLM 知道要"新增租户"，也没有工具可调。 |
| **Why 5：MCP 客户端已经实现了，为什么 Agent 用不了？** | `guanxin-v2/backend/app/mcp/client.py` 中的 MCPClient 已有完整的 `connect()` / `call_tool()` 能力，但从未注册进 Agent 的工具列表。Agent 的 `get_tools()` 只返回 kb_retrieval 和 skill_execute。 |

### 1.3 根因总结

```
┌──────────────────────────────────────────────────────────────┐
│  三大根因                                                      │
│                                                               │
│  1. 无意图分类 — LLM 一次调用完成所有决策，System Prompt 误导  │
│  2. 无操作工具 — 只有检索工具，没有 CRUD / 业务操作的 Skill    │
│  3. MCP 未集成 — MCPClient 已实现但未注册进 Agent 工具列表    │
└──────────────────────────────────────────────────────────────┘
```

### 1.4 架构层面的根本缺陷

当前 `create_react_agent` 是一个黑盒，内部是固定的 ReAct 循环（Tool-calling → execute → observe → tool-calling）。它没有给开发者留下插入意图分类、模式决策的"钩子点"。一切决策权交给 LLM，而 LLM 又受 System Prompt 的影响。

**升级到自定义 StateGraph 后**，每个节点是可控制的逻辑节点，可以在 LLM 调用之前做规则匹配 → 意图分类 → 模式决策，然后才根据决策结果走不同的执行路径。

---

## 2. 用户故事（升级后的体验提升）

### 2.1 意图识别体验

| 编号 | 用户故事 | 与当前对比 |
|------|---------|-----------|
| US-UP-1 | As a 用户, I want 说"新增租户"时 Agent 识别这是一个操作意图、弹出表单让我填写, so that 我不需要知道"这个操作需要什么工具" | 当前：Agent 去查知识库，返回可能不相关的文档片段 |
| US-UP-2 | As a 用户, I want 问"有哪些租户"时 Agent 直接调用查询工具返回结果, so that 查询类问题秒出结果 | 当前：Agent 也先去 kb_retrieval，再做一层 LLM 回答 |
| US-UP-3 | As a 用户, I want 问"租户的概念是什么"时 Agent 检索知识库回答, so that 概念性/知识性问题走知识库 | 当前：这条其实是对的，保留此能力 |
| US-UP-4 | As a 用户, I want 闲聊时 Agent 不调用任何工具直接回复, so that 不浪费工具调用 tokens 和时间 | 当前：Agent 可能也去 kb_retrieval |

### 2.2 工具能力体验

| 编号 | 用户故事 | 与当前对比 |
|------|---------|-----------|
| US-UP-5 | As a 用户, I want Agent 能调用已注册 Skill 完成具体任务（如数据分析、文本处理）, so that 复杂任务一步完成 | 当前：skill_execute 工具存在但全靠 LLM 判断何时调用 |
| US-UP-6 | As a 用户, I want Agent 能调用已连接的 MCP 服务器工具, so that 外部系统能力融入对话 | 当前：MCPClient 代码写好了但 Agent 不可调用 |
| US-UP-7 | As a 开发者, I want MCP Server 连接后工具自动注册进 Agent, so that 不用手动维护工具列表 | 当前：需要手动配置 enabled_tools |

### 2.3 交互模式体验

| 编号 | 用户故事 | 与当前对比 |
|------|---------|-----------|
| US-UP-8 | As a 用户, I want 多个操作步骤时 Agent 逐步引导我完成, so that 不会遗漏必填参数 | 当前：Agent 多轮追问靠 LLM 记忆，无结构化状态管理 |
| US-UP-9 | As a 用户, I want 操作前 Agent 弹出确认卡片让我确认, so that 不可逆操作有安全网 | 当前：无确认机制 |
| US-UP-10 | As a 用户, I want 操作结果以卡片形式展示而非纯文本, so that 信息层次分明 | 当前：工具结果靠 LLM 润色后纯文本输出 |

---

## 3. 需求池（P0/P1/P2 分级）

### 说明

本次需求编号采用 **UP-XXX**（UP = Upgrade），与 v2 原 PRD 中 AG-XXX 的 Demo 需求形成对照。原 AG-001 到 AG-005 在本轮升级后自然实现，但能力范围被扩展。

### 3.1 P0 — 必须实现：核心链路重构

| ID | 需求标题 | 需求描述 | 验收标准 | 依赖文件 |
|----|---------|---------|---------|---------|
| UP-001 | 意图分类：正则 + LLM 双层路由 | 将用户消息经过正则匹配（快速分类明确意图）和 LLM 分类（兜底语义理解）两层，输出意图标签：chat / knowledge_query / data_query / single_create / single_update / single_delete / batch_operation / multi_step_flow / system_diagnosis / ticket_submit | 1. "今天天气怎么样" → chat<br>2. "什么是租户隔离" → knowledge_query<br>3. "查一下所有租户列表" → data_query<br>4. "新增一个租户" → single_create<br>5. "修改 tenant-a 的名称" → single_update<br>6. "删除租户 tenant-x" → single_delete<br>7. "批量导入 100 个租户" → batch_operation<br>8. "给所有活跃租户升级套餐" → multi_step_flow<br>9. "系统为什么慢了" → system_diagnosis<br>10. "帮我提个工单" → ticket_submit | `graph.py`（新增 IntentParser 节点）<br>`prompts.py`（新增意图分类 prompt） |
| UP-002 | 模式决策：根据意图决定交互模式 | 基于 UP-001 的意图标签，决定交互模式：chat（自由对话）、direct（直接执行）、confirm（需用户确认后执行）、form（弹表单补全参数）、multi_step（多步编排）。**v2 Demo 阶段简化**：chat/direct/confirm 三种模式 | 1. chat → 走 ChatResponder 节点，自由对话<br>2. knowledge_query → direct，静默执行 kb_retrieval + 汇总<br>3. data_query → direct，静默执行查询工具<br>4. single_create → confirm/form（视参数完整度）<br>5. single_update → confirm/form（视参数完整度）<br>6. single_delete → confirm<br>7. batch_operation → confirm<br>8. multi_step_flow → multi_step（启动 ReAct 子 Agent）<br>9. system_diagnosis → direct<br>10. ticket_submit → form | `graph.py`（新增 ModeDecision 节点） |
| UP-003 | 工具注册增强：Skill + MCP 全部注册进 Agent 工具列表 | `get_tools()` 返回的工具列表不仅包含 kb_retrieval 和 skill_execute，还应包含：<br>1. 所有已注册 Skill 的调用工具（每个 Skill 一个 tool）<br>2. 所有已连接 MCP Server 的工具（mcp__{server}__{tool_name}） | 1. 在对话中说出 Skill 名称，Agent 可调用对应 Skill<br>2. MCP Server 连接后，Agent 对话可调用其暴露的工具<br>3. 断开 MCP Server 后对应工具从 Agent 工具列表移除<br>4. `tools.py` 中 `get_tools()` 返回值包含动态发现列表 | `tools.py`（工具注册逻辑重构）<br>`mcp/client.py`（暴露 tool_list 接口） |
| UP-004 | 自定义 StateGraph：替代 create_react_agent | 用 `langgraph.StateGraph` 构建自定义 Agent 图，包含以下节点：<br>1. IntentParser（意图分类）<br>2. ModeDecision（模式决策）<br>3. ChatResponder（聊天回复）<br>4. ReActToolExecutor（ReAct 工具执行，相当于现有 create_react_agent 的能力）<br>5. 条件路由边 | 1. 对话功能不受影响，流式输出正常<br>2. 不同意图走不同节点路径<br>3. tool_call 和 tool_result SSE 事件正常发送<br>4. 推理链展示正常<br>5. 图编译成功，无循环路径无死节点 | `graph.py`（完全重写） |

### 3.2 P1 — 应尽快实现：重要增强

| ID | 需求标题 | 需求描述 | 验收标准 | 依赖文件 |
|----|---------|---------|---------|---------|
| UP-101 | FlowLauncher 支持 interrupt/resume | 多步流程场景下，ReAct 子 Agent 执行到需要用户输入时暂停（interrupt），用户提交输入后继续（resume）。与 guanxin-sdk 的 interrupt 机制对齐。 | 1. 多步流程触发后，某个步骤弹出表单 → Agent 等待<br>2. 用户提交表单后 Agent 继续执行后续步骤<br>3. interrupt 时对话状态保留在上下文 | `graph.py`（新增 FlowLauncher 节点）<br>新增 `flow/` 模块 |
| UP-102 | MCP 工具动态发现 | MCP Server 连接成功后，Agent 工具列表自动更新，无需手动重启 Agent 或重新配置 enabled_tools。支持运行时新增/移除 MCP 工具。 | 1. 新增 MCP Server 连接 → Agent 工具列表自动增加<br>2. 断开 MCP Server → Agent 工具列表自动移除<br>3. 工具列表变更不需要重启应用 | `mcp/client.py`（发布工具变更事件）<br>`tools.py`（订阅工具变更） |
| UP-103 | ContextLoader 节点加载用户画像 | 在图执行的第一步加载当前用户的相关上下文：<br>1. 对话历史（已有）<br>2. 用户画像（租户角色/权限摘要）<br>3. 最近操作记录<br>4. 当前租户上下文 | 1. 不同租户的对话，Agent 能感知租户名称<br>2. 不同权限角色，Agent 给出的选项不同<br>3. 上下文随 conversation_id 正确切换 | 新增 `agent/context.py`<br>`graph.py`（新增 ContextLoader 节点） |

### 3.3 P2 — 可后续实现：锦上添花

| ID | 需求标题 | 需求描述 | 验收标准 |
|----|---------|---------|---------|
| UP-201 | 多轮澄清 | 当用户输入意图模糊（如"帮我处理一下"），Agent 主动追问澄清而不是猜测执行。 | 1. 模糊输入触发追问<br>2. 用户澄清后 Agent 走正确路径<br>3. 追问不超过 3 轮 |
| UP-202 | 权限感知 | IntentParser 和 ContextLoader 协作，识别到无权限操作时提前拦截并友好提示，不走到工具调用再报错。 | 1. 无权限操作 → Agent 直接告知"您没有此操作权限"<br>2. 有权限列举 → Agent 提示"您可以执行以下操作" |
| UP-203 | Flow 超时管理 | 多步 Flow 或 ReAct 子 Agent 设置最大执行步数和超时时间，超时后优雅降级（告知用户进度、保存草稿、支持续作）。 | 1. 超时后不报 500，而是生成友好提示<br>2. 已完成的步骤不被回滚<br>3. 用户可查看执行到哪一步 |

---

## 4. 与现有设计文档的关系

### 4.1 与 guanxin-sdk U2A2S 设计的对齐

```
guanxin-sdk/docs/u2a2s/03-tech-design-agent.md          guanxin-v2（本次升级）
┌─────────────────────────────────────────────┐          ┌──────────────────────────────────────────┐
│  ContextLoader → IntentParser → ModeDecision │          │  ContextLoader(P1) → IntentParser(P0) →   │
│       → DirectExecutor / ReActSubAgent /     │  ────→  │  ModeDecision(P0) →                      │
│         FlowLauncher (含 interrupt)          │  对齐    │  ChatResponder / ReActToolExecutor(P0) /  │
│       + 工具发现 + 权限感知 + 异常处理        │          │  FlowLauncher-without-{Flow引擎}(P1)       │
└─────────────────────────────────────────────┘          │  + MCP工具注册(P0) + 动态发现(P1)          │
                                                         └──────────────────────────────────────────┘
```

**关键差异**：

| 维度 | guanxin-sdk 设计（全功能版） | v2 本次升级（Demo 增强版） |
|------|---------------------------|--------------------------|
| Flow 引擎 | Agent 启动服务端 Flow，处理 interrupt/resume | v2 无 Flow 引擎，FlowLauncher 简化为 ReAct 子 Agent |
| 工具来源 | OpenAPI 元数据动态发现 + MCP 工具 | Skill 注册表 + MCP 工具（手动或动态发现） |
| 权限感知 | 调用前查询权限网关 | P2 阶段不做 |
| DirectExecutor | 将意图直接映射为 Tool 调用 | 由 ReActToolExecutor 接管（复用现有 ReAct 能力） |
| 四模式交互 | 对话直接/确认/表单/编排 | v2 Demo 阶段简化：chat/direct/confirm 三种 |

### 4.2 与 guanxin-v2 原 PRD 的关系

| 原需求 ID | 原描述 | 本次升级后如何覆盖 |
|-----------|--------|-------------------|
| AG-001 | 多轮对话 | UP-004 自定义 StateGraph 保留多轮对话能力，ContextLoader(P1) 增强上下文 |
| AG-002 | 流式输出 | UP-004 的 ReActToolExecutor 节点复用现有 astream_events 机制 |
| AG-003 | 工具调用（3 类工具） | UP-003 工具注册增强，MCP 工具接入后工具种类远超 3 类 |
| AG-004 | 推理链展示 | UP-004 ReActToolExecutor 保留 tool_call / tool_result SSE 事件 |
| AG-005 | Agent 配置 | 不受影响，配置项可扩展（如是否启用意图分类的 LLM 层） |
| AG-006 | 上下文窗口管理 | 不受本次升级影响 |
| AG-007 | 多 Agent 配置 | 不受本次升级影响 |
| AG-008 | Agent 记忆持久化 | 不受本次升级影响 |

---

## 5. 待确认问题

| 编号 | 问题 | 影响范围 | 建议方向 |
|------|------|---------|---------|
| Q-UP-1 | FlowLauncher 在 v2 Demo 阶段是否需要 interrupt/resume，还是简化为"多步 ReAct 子 Agent 一次性跑完"？ | UP-101 的复杂度 | 建议 P0 简化为 ReAct 子 Agent（走完输出结果），P1 再加 interrupt/resume |
| Q-UP-2 | 意图分类的"正则层"正则规则如何定义？是写死在代码中，还是做成可配置的规则文件？ | UP-001 的实现方式 | 建议 P0 写死在代码（规则不超过 20 条），P1 抽象为配置文件 |
| Q-UP-3 | ModeDecision 在 Demo 阶段需要支持 form 模式吗？form 模式需要前端 A2UI 能力配合。 | UP-002 / A2UI 模块 | 建议 P0 仅 chat/direct/confirm 三种，form 和 multi_step 在 P1 与前端协同启动 |
| Q-UP-4 | MCP 工具注册是默认全部注册，还是支持按 Server/Tool 级别启用/禁用？ | UP-003 / MCP 模块 | 建议 P0 全部注册（Demo 阶段 MCP Server 数量有限），P1 加启用控制 |
| Q-UP-5 | ContextLoader 加载的"用户画像"在 Demo 阶段的数据来源是什么？v2 是否有用户表/permission 表？ | UP-103 的实现前提 | 建议 P0 跳过 ContextLoader，直接从 conversation_id 获取 tenant_id 即可；P1 补齐 |
| Q-UP-6 | 升级后是否需要保留 create_react_agent 的回退能力？还是完全替代？ | UP-004 的部署安全性 | 建议添加环境变量 `AGENT_MODE=legacy` 可切回旧版 create_react_agent，确保平滑升级 |
| Q-UP-7 | Skill 注册为 Tool 的方式：是每个 Skill 一个独立 tool（如 skill_data_summary），还是统一的 skill_execute 并传入 skill_name？ | UP-003 的工具设计 | 建议每个 Skill 独立注册为 tool（与 MCP 工具注册方式一致），便于 LLM 理解和选择 |
| Q-UP-8 | 意图分类是否需要在每次对话中都调用 LLM 分类层？还是只在正则层未命中时才调用？ | UP-001 的延迟和成本 | 建议正则命中时跳过 LLM（节约 tokens + 降低首 token 延迟），未命中时走 LLM 兜底 |

---

## 6. 验收标准总览

### 6.1 P0 上线必须通过的场景

| 编号 | 场景 | 预期行为 | 涉及需求 |
|------|------|---------|---------|
| SC-01 | 用户说"你好" | ChatResponder 直接回复，不调用任何工具 | UP-001 + UP-002 + UP-004 |
| SC-02 | 用户问"什么是知识库分段" | IntentParser → knowledge_query → ReActToolExecutor → 调 kb_retrieval → 汇总回答 | UP-001 + UP-002 + UP-004 |
| SC-03 | 用户说"查一下有哪些注册的 Skill" | IntentParser → data_query → ReActToolExecutor → 调列表查询 → 返回结果 | UP-001 + UP-002 + UP-004 |
| SC-04 | 用户说"新增一个租户" | IntentParser → single_create → ModeDecision → confirm → 提示操作确认 / 如 demo 阶段只读则走 direct 告知"demo 不支持" | UP-001 + UP-002 + UP-004 |
| SC-05 | MCP Server 已连接，用户说"用天气工具查北京天气" | IntentParser → data_query → ReActToolExecutor → 调 mcp__weather__get_weather → 返回结果 | UP-001 + UP-003 + UP-004 |
| SC-06 | 原有对话功能（知识库问答）不受影响 | 上传文档后对话问答正常工作，推理链正常展示，流式输出正常 | UP-004 |

### 6.2 P0 不通过的场景（已知限制）

| 编号 | 场景 | 限制说明 |
|------|------|---------|
| SC-NO-01 | 批量导入 100 个租户 | v2 无 Flow 引擎，batch_operation 意图走 confirm 模式但无实际执行工具 |
| SC-NO-02 | 多步流程中断后恢复 | FlowLauncher 的 interrupt/resume 是 P1 需求 |
| SC-NO-03 | 弹表单补全参数 | form 模式需要 A2UI 前端协同，P1 启动 |

---

*本文档为 Draft 状态，待团队评审后定稿。下一步交由架构师高见远进行系统设计与任务分解。*
