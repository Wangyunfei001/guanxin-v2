# 观心 LangChain 原生执行链迁移

用户已确认：取消 assistant-ui 与 AI SDK，以 LangChain React SDK、Deep Agents、LangGraph 收敛实现，优先减少自研 Agent 代码。

## 决策

保留 React/Next.js 与现有基础组件；采用 @langchain/react 官方 HttpAgentServerAdapter。FastAPI 保留业务鉴权，并提供该适配器所需的线程状态、命令、事件订阅接口。Python Deep Agents 接管普通聊天、只读工具循环与研究；使用既有 SQLite checkpointer。业务写操作继续调用已有工作流引擎，保留审批、权限复核与 uncertain 恢复。

备选为引入独立 Agent Server 或继续 AI SDK 适配。前者增加部署迁移范围，后者保留重复协议。本轮采用官方前端 HTTP 适配器和最小业务服务接口；不实现自研前端 Agent 状态机，不复制官方消息组装逻辑。

## 数据与权限

conversation_id 对应唯一 LangGraph 线程，服务端校验 owner，客户端不能指定 tenant/user/model/tool 权限。旧消息作为只读历史显示，首次接管线程导入文本上下文，不重放旧工具调用。新执行保存完整 checkpoint，前端由官方 SDK 获取状态。虚拟文件限定在任务状态内，禁止宿主 shell。工具目录按当前账号和租户配置构造，业务写工具不进入通用 Agent。

命令启动后台任务，订阅关闭不取消任务；显式停止才取消。事件需要支持重连重放，服务重启将未完成运行标记中断，用户可基于 checkpoint 继续；不声称本轮具备多进程分布式调度或自动重放外部写操作。

## 界面

保留会话列表、输入、Markdown、工具结果、业务审批/补充参数/取消/uncertain 处置、研究来源和报告文件。复用基础组件，不引入新设计平台。SDK 负责运行状态与流式消息；业务卡片仅负责业务显示和调用。

## 验收

固定依赖；用真实 Deep Agents 图加可控模型测试多轮工具、checkpoint 恢复、租户隔离、错误和取消；HTTP 协议需使用实际 JS SDK 验证。前端 typecheck/build，浏览器验证输入、流式结果、刷新恢复、审批与报告。新链路通过后移除旧前端依赖与已失去入口的 AI SDK 后端协议。其余旧业务模块只在确认无人引用后删除。

## 分期

本轮实施原生链路与依赖清理。后续独立迭代：生产级多 worker 调度、业务写流程进一步声明式化、全部旧消息结构迁移及版本化技能。每阶段以实际测试和删除重复实现为验收，不能将依赖安装视为完成。
