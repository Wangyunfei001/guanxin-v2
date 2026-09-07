# 观心 v2：从 Agent Demo 到企业任务执行平台

Claude Code · LangChain Deep Agents · DeepSeek Harness

架构研究与迭代路线 | 2026-09-04 | 面向产品与技术负责人

## 建议决策

**保留观心的平台与业务控制层，以可验证的任务交付为目标，渐进建设自己的运行时边界；将 Deep Agents SDK 作为复杂任务执行器候选，将 Claude Code 作为交互与任务闭环参照，将 DeepSeek Harness 作为模块化架构参照。**

当前优先级是任务、产物、上下文和可靠执行。直接替换整个后端、复制终端编码产品，或先建设通用多 Agent 编排，都不能由现有证据证明有更高收益。

## 最终目标

观心成为企业内部可治理的 AI 工作平台：用户给出目标与授权资料，系统制定必要的计划、调用工具、交付可核查产物，并把经过确认的行动落到业务系统；长任务能继续、费用可约束、结果可追溯、责任可交接。

## 未来一个阶段最重要的成果

交付一个真正可试用的“研究与分析工作台”：同事可以提交资料和问题，获得带来源的报告及行动草稿，查看任务进度、历史版本、失败原因与运行成本。先证明一个高频场景持续有人使用，再扩展到真实业务写操作。

## 阅读边界

本文是决策建议，未批准实施、未进行依赖升级或生产部署。以 guanxin-v2 的 a59fd0c 封版提交及本轮本地代码核对为基线；已有前端工作区修改未纳入能力验收。外部文档按访问日解读，版本号与默认行为在实施时须再次锁定。

假设两名工程师投入、产品与测试人员兼职协作，首批为少量内部用户。时间范围是工作量估算，业务场景、人员和模型预算仍待确定。本轮未运行第三方框架基准，不宣称某个框架更快、更便宜或更准确。

---PAGE---

# 01 现有基础与真正的缺口

观心已经具备有价值的技术底座。下一轮应围绕它做增量建设，而不是把已验收链路重新实现一遍。

| 领域 | 本轮确认的状态 | 对演进的含义 |
| --- | --- | --- |
| Agent 执行 | Supervisor 区分直接回答、只读工具、研究与写工作流；只读循环上限为 4 回合 / 8 次调用 | 保留轻量路径；长任务另设可配置预算与执行器 |
| 权限与工具 | Tool Catalog 按租户配置、角色和风险过滤；写工具走工作流 | 作为所有候选执行器必须遵守的控制边界 |
| 工作流恢复 | LangGraph checkpoint、参数表单、审批、幂等记录、uncertain 人工接管已存在 | 将恢复扩展到一般任务；不能据此承诺外部写入全局 exactly-once |
| 知识与研究 | 文档解析、向量检索、来源、预算、研究状态持久化已实现 | 优先产品化报告交付和证据核查 |
| 会话上下文 | UI parts 可保存；普通对话重新给模型组装历史时使用全部 role/content，未见此路径的预算化压缩与完整工具历史投影 | UI 恢复与模型继续工作是两种能力，需要分别验收 |
| 运行与产物 | 研究在 HTTP 流生成器中直接执行；有研究专用记录，未见统一持久任务 worker 和通用产物服务 | 建设任务执行与浏览器连接解耦的机制，不仅增加代理超时 |
| 身份与上线 | 登录用户/API Key 为进程内预设；当前定位为本地 Demo | 内部多人试用前补真实账号、密钥撤销、审计、配额、备份恢复 |

以上基于静态代码核对，未做本轮断网、进程崩溃或并发实验。对“尚未具备”的判断限定在已检查的主链路。

本地验收报告记录七组真实依赖场景、151 项后端测试、4 项 Chromium 场景通过；这是已有验收证据，本轮未重跑，也未重新核对 GitHub 最终发布状态。

证据：[封版验收报告](/Users/wyf/workspace/aicoding/guanxin-v2/docs/releases/v0.2.0-demo-acceptance.md)、[执行器](/Users/wyf/workspace/aicoding/guanxin-v2/backend/app/agent/executor.py)、[工具目录](/Users/wyf/workspace/aicoding/guanxin-v2/backend/app/agent/tool_catalog.py)、[流式接口](/Users/wyf/workspace/aicoding/guanxin-v2/backend/app/api/aisdk.py)、[工作流引擎](/Users/wyf/workspace/aicoding/guanxin-v2/backend/app/workflows/engine.py)、[身份存储](/Users/wyf/workspace/aicoding/guanxin-v2/backend/app/models/tenant.py)。

---PAGE---

# 02 三个参考项目分别提供什么

## Claude Code：学习任务完成方式

官方将核心行为描述为收集上下文、采取行动、验证结果，并依据结果继续调整。终端、桌面、IDE 与 Web 等入口共享底层循环。会话恢复、上下文压缩和跨会话记忆属于不同机制；文件检查点不覆盖数据库、API 或部署副作用。[Anthropic：How Claude Code works](https://code.claude.com/docs/en/how-claude-code-works)

用户提供的中文页面是第三方架构说明，其中“无 GUI”等定位与现行官方文档不同。本文只将其作为发现入口，不以其内部文件名、逆向分层或版本宏作为官方架构证据。[Claude Code Architecture：中文入口](https://ccb.agent-aura.top/docs/introduction/what-is-claude-code)

## Deep Agents：评估可嵌入的执行器

用户链接指向 Deep Agents Code，即 dcode 终端产品。应评估的集成对象是独立的 Deep Agents SDK。它构建在 LangChain 与 LangGraph 上，组织文件上下文、子任务和记忆等能力。当前文档说明 v0.7 起规划为可选项，需显式配置 TodoListMiddleware。[LangChain：Code 产品](https://docs.langchain.com/oss/deepagents/code/overview)、[SDK 概览](https://docs.langchain.com/oss/python/deepagents/overview)

## DeepSeek Harness：学习模块边界

官方仓库确认它由 DeepSeek 开发，基于 Cordis，采用插件化组合；目前仍为开发者预览，明确提示不兼容变更。架构将模型、工具、循环、持久化等能力分开组合，会话事实与运行时扩展事件也有区分。[DeepSeek：仓库说明](https://github.com/deepseek-ai/deepseek-harness)、[架构参考](https://deepseek-harness.github.io/deepseek-harness/reference/)

| 参照对象 | 对观心最有价值的借鉴 | 建议采用方式 |
| --- | --- | --- |
| Claude Code / Agent SDK | 持续验证、用户中途纠正、任务上下文管理 | 先借鉴产品机制；如需编码专长，再单独评估 SDK |
| Deep Agents SDK | 长任务的文件上下文、摘要、子任务与框架集成 | 独立实验，通过共同验收集后局部接入 |
| DeepSeek Harness | 能力服务接口、执行前后策略、事件事实与投影 | 先借鉴接口设计；运行时接入后置且隔离 |

“deep agent”是能力范式，Deep Agents 是具体库，dcode 是产品，harness 是围绕模型的执行与控制系统。它们不能作为同一层的三个替换件直接比较。

---PAGE---

# 03 定位与首个完整业务场景

## 选择企业任务平台作为主方向

候选方向有三种：个人编码助手、通用 harness 基础设施、企业任务执行平台。前两者分别要求更深的开发环境体验和框架生态投入；观心已有租户、知识、审批与结构化业务工具，更适合从第三种方向形成价值。这是基于现有资产的工程判断，仍需真实用户验证。

产品首先服务知识、研究、数据整理和运营流程。编码与浏览器操作是按需求接入的执行能力，不必成为首版主界面或默认工具。

## 用本次研究任务作为产品样本

用户输入“结合这几份资料，研究系统演进路线”，系统应完成：

1. 建立任务，记录目标、输入、交付格式、验收标准和预算。
2. 检索授权资料与公开来源，记录证据、冲突与缺口。
3. 形成报告、路线和行动草稿，给出每项关键判断的依据。
4. 用户查看文件、版本差异、来源及运行消耗，并提出修改。
5. 系统继续同一任务，保留上下文；用户明确要求后，才将具体行动写入外部系统。

第一阶段只交付报告和行动草稿，支持下载与修订。真实工单、CRM 或消息平台写入放在后续可控阶段，并绑定目标系统的回执。

## 产品形态建议

保留对话作为入口，增加任务列表、运行详情、产物区和待处理决定。用户需要看到“正在做什么、已得到什么、为何暂停、下一步需要谁”，无需理解 LangGraph、MCP 或内部 middleware。

完成状态分开记录：运行正常结束、产物验证通过、业务负责人验收通过。模型的最终一句话不能独自决定任务是否成功。

## 价值衡量

核心指标是被用户接受的任务完成率、有效节省时间和每个合格结果的总成本。消息数量、工具数量或子 Agent 数量仅作诊断信息。

v1.0 应表示至少两个真实场景可以持续交付，具备可测量的质量、权限、恢复与运维能力。它不等于“集齐所有参考产品功能”。

---PAGE---

# 04 建议的目标架构

**平台管理任务和责任，执行器完成受限工作，工具网关负责副作用，产物服务保存交付结果。** 以下全部为拟议设计。

:::architecture

## 平台层保持稳定

FastAPI 继续拥有认证、租户与用户授权；现有 AI SDK / assistant-ui 继续承担交互。新建最小 TaskRun 和 Artifact 服务，关联现有 conversation、workflow 和 research 标识，不在第一轮改写全部历史表。

TaskRun 建议包含 goal、owner、inputs、budget、status、executor_version、parent_run_id。Artifact 建议包含所属运行、版本、内容哈希、来源、类型、校验结果和存储位置。产物下载也必须经过归属校验。

## 执行器作为可替换实现

先为当前执行路径定义一个薄适配接口，例如 start、resume、cancel、get_state 和 stream_events。研究候选实现可使用 Deep Agents；其他执行路径继续使用现有实现。稳定接口以实际出现的第二种实现为边界，避免预先开发完整插件框架。

## 用增量事件统一观察，不急于全面事件溯源

记录 run/step/tool/approval/artifact 的关键持久事实，使用 run_id、event_id、递增 sequence、schema_version 和父子关系。进度通知和展示快照从这些事实生成。DeepSeek Harness 的事实日志与投影分离值得参考，但其完整 Cordis/Typert 架构没有必要整体迁入 Python 平台。[DeepSeek：架构参考](https://deepseek-harness.github.io/deepseek-harness/reference/)

业务状态与关键事件优先在同一数据库事务提交；跨存储副作用用幂等键、回执和对账处理。LangGraph checkpoint 存执行位置，任务表存业务状态，两者通过运行 ID 和恢复规则关联，不能互相冒充唯一事实来源。

## 统一权限的最后一关

所有工具调用，包括框架自带文件工具和子 Agent 调用，都进入同一可审计政策。调用方身份由服务端注入。宿主服务持有业务凭据；执行器只得到完成任务所需的能力。模型提供的 tenant_id、角色或许可文本不改变授权。

---PAGE---

# 05 上下文、记忆与技能应如何演进

## 先解决上下文失真与无限增长

本地普通对话组装将历史转换为 role/content，说明保存完整 UI parts 不等于下一轮模型能恢复同样的工具事实。建议引入 ContextBuilder：明确系统约束、当前目标、近期对话、已核验结果和按需材料；将旧工具输出转为可检索引用，并保存原文。[本地执行器](/Users/wyf/workspace/aicoding/guanxin-v2/backend/app/agent/executor.py)

| 层次 | 应保存什么 | 规则 |
| --- | --- | --- |
| 权限与政策 | 身份、角色、资源范围、工具风险 | 确定性配置，不由摘要决定 |
| 运行事实 | 工具调用、审批、来源、回执 | 持久化；可追溯，不被摘要覆盖 |
| 工作上下文 | 当前目标、约束、阶段结果 | 有 token 预算；可重新构建 |
| 工作文件 | 长报告、检索结果、分析中间数据 | 按任务隔离，按需读取 |
| 长期记忆 | 用户偏好、项目约定、经验 | 显式归属、来源、版本、删除能力 |
| 业务知识库 | 可授权检索的组织文档 | 由资料维护流程更新，保留出处 |

Claude 的记忆文档强调记忆是上下文而非强制配置；其 Skills 支持按需加载。Deep Agents 的上下文机制包括长结果卸载与摘要，但具体阈值是版本实现细节，不适合作为观心不可变的产品规则。[Anthropic：Memory](https://code.claude.com/docs/en/memory)、[Skills](https://code.claude.com/docs/en/skills)、[LangChain：Context engineering](https://docs.langchain.com/oss/python/deepagents/context-engineering)

## 区分技能说明和可执行工具

当前 BaseSkill 是 Python 可执行插件。建议新增“工作方法包”，以 SKILL.md 和资源描述目标、步骤、输入、产物格式与验证样例，并以独立 manifest 保存版本、工具需求和批准范围。方法包组合工具，不能通过提示词获得更高权限。[本地 BaseSkill](/Users/wyf/workspace/aicoding/guanxin-v2/backend/app/skills/base.py)

先做三份方法包：资料研究、知识问答、表格分析。每份附带少量真实验收样本。共享记忆不默认从聊天自动写入；先让用户确认稳定事实，并提供查看与删除入口。

多用户 StoreBackend 必须显式定义 namespace。本系统建议至少区分租户、用户或项目、用途；身份来自运行上下文，不来自模型参数。[LangChain：Backends](https://docs.langchain.com/oss/python/deepagents/backends)

---PAGE---

# 06 长任务与外部行动的可靠性

## 将任务生命期与浏览器连接分开

当前研究直接在请求流中执行。建议由 TaskRun 接收任务、持久队列交给 worker、浏览器订阅事件。关闭页面只断开订阅；取消任务是另一个显式动作。重连依据 sequence 补齐事件，而不是重新提交一次任务。[本地 AI SDK 接口](/Users/wyf/workspace/aicoding/guanxin-v2/backend/app/api/aisdk.py)

第一版可以是单 worker 与数据库队列，但应有任务领取、租约、heartbeat 和过期任务处理；不能把进程内 create_task 当作持久队列。多 worker 出现后再扩展并发存储与协调方案。

## 恢复按副作用分类

| 场景 | 建议恢复行为 |
| --- | --- |
| 只读检索超时 | 在剩余预算内有限重试，保留失败事实 |
| 等待补充信息/审批 | 恢复同一运行与决定；重新检查当前权限 |
| 文件产物发布 | 先临时生成、校验，再提交版本；幂等发布 |
| 外部写入已收到回执 | 保存回执，恢复时返回已完成结果 |
| 写入后崩溃但无回执 | 先查询外部状态；无法确定则 uncertain 人工接管 |

观心现有工作流已经处理审批和不确定状态，应保留并扩展。所谓“恢复”不能被理解为重复播放所有工具调用。Claude 的文件检查点也不覆盖外部系统变化。[本地工作流引擎](/Users/wyf/workspace/aicoding/guanxin-v2/backend/app/workflows/engine.py)、[Anthropic：Checkpoints 边界](https://code.claude.com/docs/en/how-claude-code-works)

## 每次批准绑定一个具体动作

绑定 actor、run_id、tool_call_id、目标资源、规范化参数摘要、版本和有效期。参数或权限改变后重新判断批准是否仍有效。优先在 Tool Gateway 完成执行前鉴权与参数校验，执行后记录回执；后置钩子不能撤销已经发生的副作用。[Anthropic：Permissions](https://code.claude.com/docs/en/permissions)、[Hooks reference](https://code.claude.com/docs/en/hooks)、[DeepSeek：工具流水线](https://deepseek-harness.github.io/deepseek-harness/reference/tool-execution-pipeline)

## 取消与预算要覆盖整棵任务树

父运行统一分配总 token、工具调用、时间与金额上限；子任务预留预算，结束后结算。取消后禁止启动新动作；对已发出的外部写请求查询结果并说明状态，不能宣称点击取消等于回滚。模型结束、预算耗尽、阻塞和验收通过必须有不同终态。

---PAGE---

# 07 Deep Agents 接入实验怎么做

## 已发现明确版本差距

本轮可见 PyPI 发布包为 deepagents 0.7.13，2026-09-02 上传；main 的 pyproject 同为 0.7.13，要求 Python ≥3.11、LangChain ≥1.4、langchain-core ≥1.6.1。观心当前 uv.lock 与实际环境为 LangChain 1.3.13、core 1.4.9、LangGraph 1.2.9。不得据此推断直接安装兼容。[PyPI 发布记录](https://pypi.org/project/deepagents/)、[官方依赖声明](https://raw.githubusercontent.com/langchain-ai/deepagents/main/libs/deepagents/pyproject.toml)、[本地锁文件](/Users/wyf/workspace/aicoding/guanxin-v2/backend/uv.lock)

## 独立候选环境与共同契约

建立独立 lockfile 和 worker 环境，记录已解析依赖与模型配置。选取 12 个资料研究/报告任务，对比当前执行器和候选执行器；每例重复三次。先固定同一可用模型、相同工具、输入、预算和验收口径，再单独研究模型差异。

候选只得到当前租户授权的只读工具；使用任务隔离的 StateBackend 或受控 backend，暂不开放任意 shell。执行器产出文件由宿主校验后发布到 Artifact 服务。

## 不能遗漏的框架默认行为

自定义 tools 参数增加工具，不会自动移除内置能力。需显式检查候选实际暴露的文件工具、子代理和执行工具，并逐一收口。当前权限规则无匹配时允许，且不覆盖任意命令执行的 sandbox 后端；本地 FilesystemBackend 也被官方列为不适合 Web server/HTTP API。[LangChain：工具与权限](https://docs.langchain.com/oss/python/deepagents/overview)、[Backends](https://docs.langchain.com/oss/python/deepagents/backends)

HITL 依赖 checkpointer 与相同 thread_id 恢复；一次中断可能涉及多个动作。观心的审批 ID、动作顺序、用户身份及恢复语义必须经过适配测试。[LangChain：Human-in-the-loop](https://docs.langchain.com/oss/python/deepagents/human-in-the-loop)

新 event streaming 页面仍标 Beta，其 v3 事件不是 AI SDK 协议。先转换为观心自己的运行事件，再生成现有 UIMessage parts；摘要流和子任务内部输出不能混入最终回答。[LangChain：Event streaming](https://docs.langchain.com/oss/python/deepagents/event-streaming)

## 采用或停止的判据

先要求权限、审批、恢复、取消与流协议契约全部通过。再观察报告合格率、返工、延迟和有效成本是否优于基线；小样本只支持继续试点，不支持宣称普遍优胜。如果没有明显收益，继续现有 LangGraph 实现，并仅吸收验证有效的机制。

---PAGE---

# 08 版本路线与阶段门槛

版本名是建议，不代表已排期。按两名工程师与兼职产品/测试估算；范围确认后重估。各阶段以前一阶段验收为依赖，避免同时重写运行时、身份和业务流程。

| 阶段 | 预计工作量 | 核心交付 | 退出条件 |
| --- | --- | --- | --- |
| v0.3 任务与产物 | 3-4 周 | 首个研究/分析场景；TaskRun、Artifact、来源和版本；真实账号、基本审计与用量记录 | 用户独立提交、获得文件、提出修订；归属校验与关键路径通过；开始 3-5 人试用 |
| v0.4 持久执行与上下文 | 3-4 周 | worker、持久队列、重连/取消、统一预算、ContextBuilder；完成 Deep Agents 独立实验 | 断开页面不中断已接收任务；重启状态一致；长上下文不丢关键约束；决定采用或停止候选 |
| v0.5 可控业务行动 | 4-6 周 | 一个真实系统连接；具体行动审批、回执、对账；按需求加入隔离代码执行 | 代表性流程端到端完成；故障注入不盲目重放写操作；可确认实际业务结果 |
| v0.6 技能与有限协作 | 3-5 周 | 方法包版本化；2-3 个受限子任务；共享预算、取消与聚合；按需求接入第二执行器 | 多任务收益超过协调开销；权限不扩大；子任务失败可被解释或接管 |
| v1.0 可持续使用 | 前述门槛后另行评估 | 两个高频场景稳定运行；备份恢复、运维、质量回归和服务指标 | 连续 4 周观察质量、使用和成本；业务负责人确认价值；完成上线演练 |

前四阶段约 13-19 个工程周，是范围级估算，不含 v1.0 观察期及外部系统审批等待。单人兼顾全部工作时需要重新安排，不能简单沿用该时间表。

## 先后顺序的理由

产物与任务状态先让用户获得价值，也为后续运行时比较提供统一输出。后台执行和上下文随后解决长任务稳定性。真实业务写入依赖身份、审计、恢复与对账。多 Agent 只有在任务可拆、结果可验、预算可控时才有意义。

## 可以提前与应该后置的工作

Deep Agents 的短期兼容实验可以在 v0.3 末提前开展，但不阻塞基本场景交付。DeepSeek Harness 接入、通用 DAG 画布、插件市场、自动共享记忆、任意浏览器操作和自动循环优化都后置到有明确使用证据时。

---PAGE---

# 09 首个 10 个工作日的任务清单

目标是产出可评审的最小闭环和基线，覆盖 v0.3 的第一部分；不是在十天内交付整套平台。下表均为待实施建议。

| 工作日 | 负责人建议 | 工作与具体交付 | 验收 |
| --- | --- | --- | --- |
| 1-2 | 产品 + 后端 | 选定一种使用者与高频任务；收集 20 个知识/研究/分析样本；定义产物模板和评分表 | 每例有输入、预期结果、来源范围、人工基线；业务负责人认可 |
| 2-3 | 后端 | 保存当前依赖与测试基线；定义 TaskRun/Artifact/RunEvent 最小字段、状态与版本 | 文档可说明 conversation、research、workflow、checkpoint 的关联和恢复责任 |
| 3-5 | 后端 | 包装现有研究路径，记录运行、来源、结果、消耗；产物幂等发布 | 同一运行刷新后可查询；失败不得发布“成功产物”；越权读取被拒 |
| 4-6 | 前端 | 任务详情、产物下载、来源与版本；沿用现有会话与审批呈现 | 用户能找到报告、看懂状态并继续修订；不要求理解技术模块 |
| 6-7 | 后端 + 测试 | 真实身份存储与密钥生命周期设计/最小实现；归属、日志脱敏、备份路径 | 账号重启可用；密钥可撤销；新增接口隔离测试通过 |
| 7-8 | 后端 | 独立 Deep Agents 环境依赖解析与冒烟；检查内置工具、模型调用、结构化输出与事件适配 | 输出明确兼容矩阵；不污染主环境；不开放 shell 或生产写工具 |
| 9-10 | 全体 | 最小闭环演示、样本评审、回归；列出余下 v0.3 工作与候选实验差距 | 形成可复核记录、优先级和采用/继续实验/停止三选一建议 |

候选实验的 12 例 × 3 次完整对比，可在依赖冒烟成功后完成；不把它和生产身份迁移强行塞入同一天。若资源只有一人，按表中的依赖顺序执行，前端与后端不并行承诺。

## 建议首批变更范围

新增任务/产物模型、存储和 API；在现有研究结果出口增加发布适配；前端增加任务结果入口。现有工作流审批保持兼容。对执行器历史组装与统一事件的深度改造留到 v0.4。

## 本轮必须做出的三个决定

确定首批用户与最常见任务；确定内部试用环境和可使用数据；确定候选实验允许的模型与总费用上限。本文给出了默认方向，尚未将这些假设当作用户已确认的产品要求。

---PAGE---

# 10 如何证明演进确实有效

## 同一任务集、同一预算、分层验收

首批建议固定 20 个正向任务：6 个知识问答、8 个资料研究报告、6 个结构化数据分析。每例运行三次，共 60 次；另建 20 个权限与故障场景独立验收。进入真实业务写入阶段时扩充任务集并建立新基线，不混用不同范围的分母。

| 指标 | 测量方式 | 建议初始门槛，不是已达结果 |
| --- | --- | --- |
| 任务合格率 | 负责人按预设 rubric 判断是否无需重大修改；失败和超时计入分母 | 首轮 ≥48/60；成熟目标 ≥54/60，均只对固定样本有效 |
| 关键结论有证据支持 | 人工逐项核对关键事实与引用原文；缺证据须明确标注 | ≥95%；不以“链接存在”代替支持结论 |
| 权限与副作用 | 越权读写、撤权后恢复、重复审批、写后崩溃等独立用例 | 全部通过；零观察违规不代表真实世界零风险 |
| 有效成本 | 全部调用费用及失败重试费用 / 合格结果数；人工返工时间另列 | 先建基线，再由任务价值设上限；不预设虚构单价 |
| 延迟与控制 | 记录总耗时、首个有效进度时间、取消到停止新动作的时间 | 报中位数与 P95；小样本仅作诊断，目标由使用者确认 |
| 实际节省时间 | 对同类任务比较人工操作时间 + 复核返工时间 | 两周试用建议观察中位数降低 ≥30%，未达需复盘 |
| 持续使用 | 记录试用者主动复用的任务、原因和失败点 | 3-5 人中多数在第二周继续主动使用，非强制打卡 |

## 故障用例必须贴近真实执行

覆盖浏览器断开、模型超时、worker 重启、租约过期、来源不可用、超预算、取消、产物发布中断、工具权限变化、重复恢复、审批参数变化，以及外部写入成功但回执丢失。对未知结果优先显示不确定并对账。

## 多 Agent 的单独准入标准

先测试单 Agent，再对可独立拆分的资料提取或复核使用 2-3 个子任务。比较同一输入的完成率、关键遗漏、总费用、总时间和汇总损失。只有收益超过通信与复核成本才扩大使用。子任务有独立上下文并不自动形成进程或租户隔离。[Anthropic：Subagents](https://code.claude.com/docs/en/sub-agents)、[Sandboxing](https://code.claude.com/docs/en/sandboxing)

---PAGE---

# 11 技术选择、风险与调整条件

## 现在采用的原则

保留 Python/FastAPI/LangGraph 与 AI SDK 接口。保留已验证的写工作流和租户知识库。使用版本化任务与事件契约隔离框架变化；从业务任务需要出发引入能力。实际改造中只抽取受影响接口，避免为“未来可扩展”先创建大规模插件系统。

## 沙箱必须作为单独能力验收

当任务需要执行生成代码时，采用独立工作区、资源与时间限额、网络约束和受控文件导入导出。业务密钥留在平台侧，通过授权工具访问。LangChain 推荐的 sandbox-as-tool 模式可作为参照。[LangChain：Sandboxes](https://docs.langchain.com/oss/python/deepagents/sandboxes)

DeepSeek 的进程 sandbox 词汇主要定义文件效果，不包含网络和进程可见性的完整隔离承诺；其安全说明还明确表示未经过安全审计，不能当作生产就绪系统。若后续接入，应先作为可替换、隔离的实验执行器，而不承担平台唯一安全边界。[DeepSeek：Sandbox](https://deepseek-harness.github.io/deepseek-harness/reference/subsystems/sandbox)、[Safety](https://raw.githubusercontent.com/deepseek-ai/deepseek-harness/master/SAFETY.md)

## 什么时候重新考虑路线

| 观察到的情况 | 调整动作 |
| --- | --- |
| 真实需求主要是修代码、跑测试、提交 PR | 转向开发者工作台；单独比较 Claude Agent SDK 与编码执行器 |
| Deep Agents 无质量收益且引入较高升级成本 | 停止集成，保留现有实现与已验证设计 |
| 大部分业务流程稳定、确定、步骤固定 | 优先明确工作流与表单；减少自由规划 |
| 并发 worker、数据库锁或任务量成为实测瓶颈 | 再评估数据库、队列和执行调度升级 |
| 多租户与部署要求变化 | 重做隔离、凭据、数据保留和运维边界评审 |
| 真正需要多模型或多 harness 的专长 | 增加第二适配器；不把所有实现强制抽象为最低共同能力 |

Claude Agent SDK 是可编程的接入对象，不能把终端登录或订阅额度直接等同产品后端授权。后续采购、云部署或对外服务前，应按实际方案重新核对商业条款与数据要求；本文没有做价格或云服务采购比较。[Anthropic：Agent SDK overview](https://code.claude.com/docs/en/agent-sdk/overview)

---PAGE---

# 12 证据范围与结论强度

## 可以据此决策的部分

三个参考对象的层级、主要机制和显著接入边界已有官方文档支持。本地代码和锁文件支撑了现有平台能力、上下文组装、HTTP 执行绑定以及依赖差距的判断。可据此决定先做任务闭环、保留治理层、隔离候选实验。

## 仍需实验和产品确认的部分

没有运行 Claude Agent SDK、Deep Agents 或 DeepSeek Harness；没有在相同任务集上比较质量、费用或延迟。没有审计它们全部源码或验证多租户生产安全。没有确认业务系统 API、首批用户、可用数据与团队投入。路线和工期都是建议，不能作为已承诺交付日期。

Deep Agents 的包元数据保留 Beta 分类，部分官方文档有旧版迁移文字残留；本文优先使用当前明确说明与可见发布元数据，仍要求实施时锁版本验证。DeepSeek Harness 的技术预览状态已确认，本轮没有确认具体首次发布日期和统一稳定版本；不以热度或发布时间判断成熟度。

## 来源说明

全部网页访问于 2026-09-04；除 PyPI 的 0.7.13 发布记录为 2026-09-02 外，本报告所引用文档未核实到可靠的页面更新时间。抓取日期不等于发布日期。来源发布者分别为 Anthropic、LangChain、DeepSeek；中文 Claude 架构页为第三方发现资料。主文已在关键判断附近提供可点击的具体来源。

本地证据基线为 a59fd0ce0c58f3a727efb00aeb31ecd3246432fc。核对 README、封版验收报告、uv.lock，以及 agent、workflow、research、auth、conversation 和 skill 主链路。已有验收记录与本轮静态核对分开陈述；外部框架能力没有被表述为本系统已实现。

研究采用三条来源线，先读用户给定入口，再核对官方文档、依赖元数据与关键反例。停止扩展检索的原因是：剩余最重要的未知项已变成兼容性、实际收益与使用需求，这些应由实验和试用回答。

## 建议立即推进的决定

将下一阶段定义为“观心 v0.3：研究与分析任务工作台”。先用同一组真实任务证明完整交付能力；同时准备一个受限的 Deep Agents 兼容性实验。以任务结果、责任边界与用户复用来决定后续技术投入。

**最终交付对象是一项完成且可核查的工作。框架、模型与多 Agent 机制，是实现这一目标的可替换手段。**
