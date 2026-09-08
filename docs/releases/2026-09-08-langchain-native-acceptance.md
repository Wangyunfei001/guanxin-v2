# LangChain 原生迁移验收

日期：2026-09-08。分支：`feat/langchain-native-agent`。

## 已实现

- 删除 assistant-ui、AI SDK 依赖及旧流式入口；前端使用固定版本 `@langchain/react` 1.0.35 的 `useStream` / `HttpAgentServerAdapter`。
- Deep Agents 0.7.13 接管主链路的工具循环和任务文件；LangGraph checkpoint 保存执行状态。删除旧 executor、supervisor、节点编排；业务意图规则保留在 workflows 下。
- FastAPI 保留身份与业务边界，提供线程状态、命令、可重放事件、显式取消和鉴权文件下载。浏览器断开不取消后台任务。
- 保留已有业务工作流审批与幂等执行；审批时重新检查工具授权。租户和用户同时参与所有权校验。
- 支持旧对话展示、文本附件、研究模式、工具结果、Markdown 文件、失败提示和中断继续。未配置模型时明确失败。

## 协议兼容修复

Python v3 messages 事件的 `[contentEvent, metadata]` 适配为 JS HTTP adapter 的 `data` / `node`；SDK 负责消息归并。SQLite 持久化事件序号供断线重放。

Deep Agents 的 DeltaChannel 状态需通过 LangGraph `aget_state` 还原；不能直接读取 checkpoint 原始 channel_values 当作完整消息和文件。

SSE 使用初始注释、`Cache-Control: no-cache, no-transform`、`Content-Encoding: identity` 和 `X-Accel-Buffering: no`，防止代理缓冲导致前端运行状态不更新。

运行中的状态快照省略 `next`，避免 `next=[]` 被 SDK 判断为已完成而停止刷新后的订阅。取消发生在输入 checkpoint 写入前时，继续任务会补入已接受的消息。checkpointer 初始化串行化，业务图在 saver 替换后重新编译，避免并发初始化和关闭重开留下失效连接。

## 本地验证

| 检查 | 结果 |
| --- | --- |
| `cd backend && uv run pytest -q` | 152 passed；2 条官方 v3 beta 警告 |
| `npm run lint` | 通过 |
| `npm run typecheck` | 通过 |
| `npm run build` | 通过，12 个静态页面生成完成 |
| `npm run test:e2e` | 4 passed；原生模型专用 2 项在此配置下跳过 |
| `GUANXIN_E2E_AGENT_FIXTURE=1 npm run test:e2e -- e2e/native-agent.spec.ts` | 2 passed，使用真实 SDK、Deep Agents 和确定性测试模型 |

后端覆盖工具调用顺序、文件持久化、checkpointer 关闭重开、消息去重、事件重放、跨用户/租户拒绝、取消、并发拒绝、禁止委派工具、缺失模型配置，以及业务审批权限和幂等。浏览器覆盖实际报告文件下载、刷新还原、订阅断开后继续执行、显式停止后继续（消息不重复），以及原有知识库和审批流程。

浏览器截图：`frontend-react/output/playwright/native-agent-report.png`。已查看，消息、工具结果、文件入口和输入区显示正常。CI 已增加原生模型专用测试步骤。

## 尚未验收的范围

- 浏览器模型是仅在 `APP_ENV=test` 可用的测试入口；这次结果证明集成正确性，不代表真实模型的研究质量、引用准确率或费用已达标。
- 当前运行调度仅支持单进程；重启会把遗留运行标为 interrupted，需用户继续。没有跨恢复总费用预算。
- 官方 v3 流式协议仍为实验接口；升级必须重新执行协议与浏览器用例。
- 旧研究 API 为恢复历史记录保留；图片/PDF 会话附件、分支与时间旅行尚未迁移。现有知识库 PDF/DOCX 能力保留。
- 未部署、未推送远端；生产身份、分布式调度和审计不属于本次迁移。
