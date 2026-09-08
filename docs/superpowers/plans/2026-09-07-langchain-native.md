# LangChain Native Migration Implementation Plan

**Goal:** 用官方 React SDK 和 Deep Agents 接管观心主交互链，删除 assistant-ui 和 AI SDK 依赖。

**Architecture:** FastAPI 负责账号与业务接口；官方 HTTP adapter 连接线程状态/命令/订阅。Deep Agents 与 SQLite checkpoint 执行只读任务；已有业务工作流保留唯一写操作责任。

**Tech Stack:** Next.js/React、@langchain/react 1.0.35、Deep Agents 0.7.13、LangGraph、FastAPI、SQLite。

## Task 1: 依赖与协议验证

- [x] 核对当前代码、现有测试和官方 SDK 源码。
- [x] 建立独立功能分支，固定 npm/Python 候选依赖并更新锁文件。
- [x] 用实际安装包验证 Python v3 事件与 JS HTTP adapter 的协议，记录兼容边界。

## Task 2: 原生后端

- [x] 新增 app/agent/deep_agent.py：绑定授权工具、配置、checkpointer 与任务虚拟文件，禁止任意 shell。
- [x] 新增 app/api/langchain.py 与运行存储：GET 线程 state、POST commands、POST stream/events；请求身份验证、顺序运行、取消、事件重放。
- [x] 对旧业务工作流提供新界面可调用的审批接口，保持既有引擎。
- [x] 测试：`uv run pytest tests/test_langchain.py -q`，覆盖多轮工具、历史、owner、取消和审批边界。

## Task 3: 原生前端

- [x] 新增 components/agent/thread.tsx，使用官方 useStream/HttpAgentServerAdapter 和基础 UI。
- [x] 调整 app/assistant.tsx，移除 AiSdkRuntimeProvider，保留会话导航。
- [x] 展示旧历史与新消息、工具结果、审批/研究卡片、任务虚拟文件。
- [x] 删除无引用的 assistant-ui 组件和 AI SDK 类型；移除对应 npm 包。
- [x] `npm run typecheck`；`npm run build`。

## Task 4: 集成与交付

- [x] 实际 JS SDK → FastAPI → Deep Agents 协议测试，使用可控模型，不伪装真实模型结果。
- [x] 回归现有业务后端测试；将旧协议测试改到新入口，保留权限与业务断言。
- [x] 浏览器验证主要链路，记录证据与未覆盖项。
- [x] 删除无引用旧入口；更新 README 启动说明与迁移限制，提交范围只包含本次改动。

## 后续演进顺序

1. **真实任务验收**：选择知识检索、资料研究、报告生成、业务审批四类固定任务，记录正确率、引用可追溯性、耗时与 token/费用；通过后再扩大使用范围。
2. **继续减少自研**：清点旧研究中断记录，完成恢复兼容迁移后删除旧研究编排；保留租户授权、业务工具、审批幂等和产品界面。不要再引入第二套 Agent 框架。
3. **运行可靠性**：有并发部署需求时优先评估 LangGraph 官方服务部署；解决持久 worker、事件保留、跨恢复预算与审计后再开放多进程。
4. **按需求补齐体验**：多模态附件、分支编辑、时间旅行分别验收；不将其与本轮依赖替换混成一次大改。

最终目标：业务团队维护工具、权限、审批规则与交互体验；通用执行、状态恢复和模型集成尽量由 LangChain / Deep Agents / LangGraph 官方能力负责。

验收记录见 `docs/releases/2026-09-08-langchain-native-acceptance.md`。
