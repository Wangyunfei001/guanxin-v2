---
id: frontend-app
type: module-design
title: 前端工作台
status: draft
parent: architecture
depends-on:
  - agent-runtime
---

# 前端工作台

## 职责

Next.js 15 App Router 单页工作台：登录、会话与流式对话、五个管理页，并把后端返回的工作流、研究证据、A2UI 与工具结果渲染成人能读的界面。

## 边界

- **不做授权判断**：按钮可见性只是体验，真正的权限在服务端；前端不缓存或推断角色能力。
- **不拼装 Agent 消息、不实现运行状态机**：流式消息、run 状态、断线重连交给官方 `@langchain/react`（`HttpAgentServerAdapter` + `useStream`）。
- 不直连后端端口：所有请求经 `/api/*` rewrite 代理到 8000，避免跨域与硬编码地址。
- 不保存业务真相：`localStorage` 只放 token、用户信息与当前会话 id。

## 契约

**路由**：`/login` 与 `(auth)` 布局；`(main)` 下 `/assistant`（会话工作台）、`/knowledge`、`/skills`、`/agent`（Agent 配置）、`/mcp`、`/a2ui`；`/chat` 永久重定向到 `/assistant`。

**数据访问**：`src/lib/api/*` 用 axios 拦截器统一附加 `Authorization: Bearer`，响应解包成 `{code, message, data}`；状态放在 zustand store（auth / agent / knowledge / mcp / skill / workflow / research / a2ui / layout）。

**错误态**：每个 store 带 `error: string | null`。**空态只在「确实没有数据」时出现**——`data.length === 0 && !error && !loading` 才渲染空态，否则渲染错误态与重试入口（`components/layout/error-state.tsx`）。网络故障不得被渲染成「知识库还是空的」这类谎报。App Router 树里必须有 `error.tsx` 与 `global-error.tsx`，一次坏响应不应摧毁整个工作台。

**登录失效**：`handleUnauthorized()` 是唯一的 401 出口，axios 拦截器与 SSE/agent 通道共用它（清 token + 跳登录页）。登录页自身返回 401 时不再跳转，避免刷新循环。`AuthGuard` 挂载时调用一次 `fetchMe()` 校验本地令牌，使过期会话在用户发起运行之前被发现。

**发送失败不丢内容**：`useStream().submit()` 不会 reject——失败被转成 stream 的 error slot。因此草稿清空必须由「命令确实被接受」驱动，失败时通过 SDK 的 `onError` 恢复草稿与附件。

**主题与设计令牌**：深色优先、可切换；主色为观心青绿（`--primary` HSL 变量，深浅两套），布局与动效令牌集中在 `src/lib/design-tokens.ts`，组件基于 shadcn/Radix。

**线程渲染**：`AgentThread` 用 `useStream` 订阅线程，按事件渲染文本、工具调用、虚拟文件下载、工作流卡片（表单 / 审批 / 取消 / uncertain 处置）、研究卡片（预算余量、主张—原文—来源）与 `query_users` 统计看板；运行中禁用输入，存在活动工作流时同样禁用。切换会话的响应带请求序号保护——只有最后一次请求的结果会被应用，先发后到的旧响应不得覆盖新选择。

**主题与设计令牌**：深色优先、可切换；主色为观心青绿（`--primary` HSL 变量，深浅两套），布局与动效令牌集中在 `src/lib/design-tokens.ts`，组件基于 shadcn/Radix。

**测试钩子**：Playwright 用例依赖稳定文案与 `data-*`/可访问名，改文案前先看 `frontend-react/e2e/`。

## 已知限制

- 图片 / PDF 会话附件未迁移，仅支持文本附件（总输入 ≤ 100000 字符）。
- 无 checkpoint 分支编辑与时间旅行 UI。
- 依赖锁文件固定版本；升级 `@langchain/react` 或 Deep Agents 需重跑原生浏览器用例。
