# 观心 v2「观心识流」UI 重设计实施计划

> 日期：2026-08-21
>
> 依据：`docs/superpowers/specs/2026-08-21-guanxin-ui-redesign-design.md`
>
> 目标：在不修改后端 API、工作流状态机和权限语义的前提下，交付深浅双主题、响应式、可访问且适合演示的完整系统 UI。

## 实施约束

- 保留 `/assistant`、`/knowledge`、`/skills`、`/agent`、`/mcp` 和 `/a2ui` 路由。
- 保留 AI SDK `UIMessage.parts`、assistant-ui runtime 和现有工作流 API。
- 不将 Canva 生成的假界面或乱码稿作为代码实现依据。
- 继续使用 shadcn/Radix 组件，不引入第二套完整设计系统。
- 主题、布局、图标和状态改造必须覆盖加载、空、错误、只读和无权限状态。
- 每个阶段通过 lint 和 TypeScript 检查后再进入下一阶段。
- 不覆盖或提交工作区中与本次任务无关的 `.gitignore` 修改。

## 阶段 1：主题、字体与基础依赖

### 目标

建立可复用的设计 Token、双主题、字体和统一图标基础，先消除页面级硬编码颜色。

### 文件

- 修改：`frontend-react/package.json`
- 修改：`frontend-react/package-lock.json`
- 修改：`frontend-react/src/app/layout.tsx`
- 修改：`frontend-react/src/app/globals.css`
- 新增：`frontend-react/src/components/theme/theme-provider.tsx`
- 新增：`frontend-react/src/components/theme/theme-toggle.tsx`
- 新增：`frontend-react/src/lib/design-tokens.ts`

### 实施

1. 添加 `@phosphor-icons/react`、`next-themes` 和本地 Geist 字体依赖；复用已安装的 `motion`。
2. 在根布局安装 ThemeProvider，默认跟随系统并持久化手动选择。
3. 将深色和浅色 Token 写入 CSS 变量，覆盖背景、表面、边框、文本、品牌色、状态色、图表色和焦点环。
4. 定义统一圆角、阴影、层级和动效时长变量。
5. 使用本地 Geist Sans 与 Geist Mono；中文回退到苹方、思源黑体和系统无衬线。
6. 为 `prefers-reduced-motion` 和减少透明效果提供全局降级。
7. 清理 `h-screen`、纯白背景、固定灰色和旧紫色登录渐变的基础样式。

### 验证

- `npm run lint`
- `npx tsc --noEmit`
- 手动验证系统主题、深色、浅色和刷新持久化。

## 阶段 2：品牌标识与应用框架

### 目标

实现品牌轨道、上下文工具栏、命令面板和响应式应用骨架。

### 文件

- 新增：`frontend-react/src/components/brand/brand-mark.tsx`
- 新增：`frontend-react/src/components/layout/app-shell.tsx`
- 新增：`frontend-react/src/components/layout/primary-rail.tsx`
- 新增：`frontend-react/src/components/layout/context-toolbar.tsx`
- 新增：`frontend-react/src/components/layout/context-panel.tsx`
- 新增：`frontend-react/src/components/layout/mobile-navigation.tsx`
- 新增：`frontend-react/src/components/layout/command-menu.tsx`
- 新增：`frontend-react/src/lib/stores/layout.ts`
- 修改：`frontend-react/src/app/(main)/layout.tsx`
- 删除或重构：`frontend-react/src/components/layout/SideNav.tsx`
- 删除或重构：`frontend-react/src/components/layout/Header.tsx`
- 修改：`frontend-react/src/app/icon.svg`

### 实施

1. 实现两条开放同心轨迹和中心节点的品牌标识，提供完整字标、图标和单色模式。
2. 实现 72px 品牌轨道，支持展开、当前模块标记、Tooltip 和键盘访问。
3. 将导航分为工作台、能力中心和系统配置，保持现有 URL。
4. 实现 56px 上下文工具栏，展示页面标题、当前 Agent、真实服务状态、租户、主题和用户菜单。
5. 使用现有 `cmdk` 实现 `Command/Ctrl + K` 命令面板，入口只包含真实可达页面和操作。
6. 实现统一 ContextPanel，通过 Store 接收来源、工具、工作流步骤和资源详情。
7. 在 768px 以下将导航和检查器切换为抽屉或 Sheet。
8. 使用 Motion 实现 160-220ms 的布局与路由过渡，并支持减少动态效果。

### 验证

- 键盘遍历品牌轨道、命令面板、主题切换和用户菜单。
- 390px、768px、1440px 下无溢出。
- 当前路由和浏览器前进后退状态正确。

## 阶段 3：图标体系迁移

### 目标

将产品可见图标统一迁移为 Phosphor，移除 Lucide 混用。

### 文件

- 修改：`frontend-react/src/app/**/*.tsx`
- 修改：`frontend-react/src/components/**/*.tsx`
- 修改：`frontend-react/package.json`
- 修改：`frontend-react/package-lock.json`

### 实施

1. 建立 Lucide 到 Phosphor 的语义映射表，不按图形相似度随意替换。
2. 导航使用 20px Regular，行操作使用 18px Regular，工具状态使用 16px Regular。
3. 选中和完成状态可以使用 Fill，其余保持 Regular。
4. 为所有纯图标按钮补充 `aria-label` 和 Tooltip。
5. 完成全量迁移后删除 `lucide-react` 依赖。
6. 扫描并禁止 Emoji 和自绘操作图标；品牌标识除外。

### 验证

- `rg -n "lucide-react" frontend-react/src frontend-react/package.json` 无结果。
- `rg -n "<button"` 抽查所有图标按钮的可访问名称。
- lint、TypeScript 和生产构建通过。

## 阶段 4：Assistant 应用骨架与会话体验

### 目标

将 Assistant 改造为品牌轨道、会话栏、主舞台和按需检查器组成的核心体验。

### 文件

- 修改：`frontend-react/src/app/assistant.tsx`
- 新增：`frontend-react/src/components/assistant-ui/conversation-sidebar.tsx`
- 新增：`frontend-react/src/components/assistant-ui/assistant-stage.tsx`
- 新增：`frontend-react/src/components/assistant-ui/assistant-empty-state.tsx`
- 修改：`frontend-react/src/components/assistant-ui/thread.tsx`
- 修改：`frontend-react/src/components/assistant-ui/aisdk-runtime-provider.tsx`
- 修改：`frontend-react/src/components/assistant-ui/reasoning.tsx`
- 修改：`frontend-react/src/components/assistant-ui/tool-group.tsx`
- 修改：`frontend-react/src/components/assistant-ui/tool-fallback.tsx`

### 实施

1. 将会话数据加载和 UI 拆分，避免 `assistant.tsx` 同时承担数据、抽屉和渲染职责。
2. 会话列表按更新时间分组，展示标题、摘要、时间和活动工作流状态。
3. 保留新建、选择、删除和最近会话恢复，不新增后端未支持功能。
4. 实现 Assistant 空状态，使用真实黄金路径命令建议。
5. 用户消息使用紧凑右侧容器；Agent 内容直接排版，不统一套大气泡。
6. 推理、来源、工具、图表和 A2UI 使用清晰层级并复用 ContextPanel。
7. 将加载、无会话、API 错误和流中断替换为匹配最终结构的状态组件。
8. 移动端会话栏改为全屏抽屉，保留输入区安全区域。

### 验证

- 刷新恢复最近会话。
- 切换会话后消息、工作流和检查器内容正确更新。
- 删除当前会话后自动选择下一会话或新建。
- AI SDK 流式输出、停止和错误恢复保持有效。

## 阶段 5：工作流轨迹与控制台

### 目标

用持续更新的工作流轨迹替代普通 Card，并让输入台根据工作流状态变形。

### 文件

- 重构：`frontend-react/src/components/assistant-ui/workflow-card.tsx`
- 新增：`frontend-react/src/components/assistant-ui/workflow-track.tsx`
- 新增：`frontend-react/src/components/assistant-ui/workflow-step.tsx`
- 新增：`frontend-react/src/components/assistant-ui/workflow-inspector.tsx`
- 新增：`frontend-react/src/components/assistant-ui/composer-dock.tsx`
- 修改：`frontend-react/src/components/assistant-ui/tool-renderers/workflow-control.tsx`
- 修改：`frontend-react/src/lib/stores/workflow.ts`
- 修改：`frontend-react/src/types/index.ts`

### 实施

1. 将顶部目标、状态和完成比例与纵向步骤轨迹分离。
2. 已完成步骤默认折叠，当前步骤展开，等待步骤降低权重。
3. 点击步骤将完整输入、输出、引用和执行记录发送到 ContextPanel。
4. 将 `waiting_input` 表单嵌入当前步骤和 ComposerDock，确保只有一个主行动区。
5. 将 `waiting_approval` 的影响范围、参数、批准和拒绝统一到审批控制台。
6. 为 `uncertain` 提供确认完成、重新执行和取消剩余流程。
7. 保留 `data-workflow` 历史恢复与现有 API，不复制状态机。
8. 使用共享布局动画表达审批转执行结果，减少动态效果时即时切换。

### 验证

- 缺参、批准、拒绝、取消、失败、重试和 uncertain 全链路。
- 刷新和后端重启后轨迹、当前步骤与可用操作恢复。
- 活动工作流期间普通输入锁定。
- 重复批准不触发重复执行。

## 阶段 6：管理页面重构

### 目标

统一知识库、Skills、MCP、Agent 配置和 A2UI 的列表、检查器和配置语言。

### 共享文件

- 新增：`frontend-react/src/components/resources/resource-list.tsx`
- 新增：`frontend-react/src/components/resources/resource-state.tsx`
- 新增：`frontend-react/src/components/resources/detail-panel.tsx`
- 新增：`frontend-react/src/components/ui/page-header.tsx`
- 新增：`frontend-react/src/components/ui/empty-state.tsx`
- 新增：`frontend-react/src/components/ui/skeleton-layout.tsx`

### 页面文件

- 修改：`frontend-react/src/app/(main)/knowledge/page.tsx`
- 修改：`frontend-react/src/app/(main)/skills/page.tsx`
- 修改：`frontend-react/src/app/(main)/mcp/page.tsx`
- 修改：`frontend-react/src/app/(main)/agent/page.tsx`
- 修改：`frontend-react/src/app/(main)/a2ui/page.tsx`

### 实施

1. 知识库改为文档列表、上传侧边面板、切片检查器和独立检索测试模式。
2. Skills 改为分类筛选、能力列表和参数详情，不显示无权发现的管理 Skill。
3. MCP 改为连接列表、Server 展开工具、分步新增面板和工具测试控制台。
4. Agent 配置改为左侧编辑、右侧能力摘要；普通用户使用语义只读视图。
5. A2UI 改为组件目录、真实预览和 Schema 编辑校验三栏实验台。
6. 为所有页面补齐骨架、空、错误、只读、无权限和保存失败状态。
7. 风险操作使用上下文确认，禁止原生 `confirm()`。

### 验证

- 保留现有 API 和 RBAC 行为。
- 管理员和普通用户分别执行 Playwright 页面检查。
- 移动端列表转换为带字段标签的纵向记录。

## 阶段 7：登录与品牌动效

### 目标

交付品牌感最强的登录体验，同时保持低成本和可访问性。

### 文件

- 修改：`frontend-react/src/app/(auth)/layout.tsx`
- 修改：`frontend-react/src/app/(auth)/login/page.tsx`
- 新增：`frontend-react/src/components/brand/flow-field.tsx`
- 新增：`frontend-react/src/components/auth/demo-accounts.tsx`

### 实施

1. 桌面端使用约 58% 品牌轨迹区和窄幅登录面板。
2. 轨迹视觉由 CSS 和轻量 Motion 组成，不加载大图或 WebGL。
3. 登录成功后品牌轨迹收束为导航标识。
4. 演示账户收纳到可展开区域。
5. 字段错误显示在字段下方，保留完整 Label 和帮助文本。
6. 移动端使用静态低成本纹理，减少动态效果时完全静止。

### 验证

- 键盘、密码管理器和自动填充正常。
- 错误文本和输入对比度达到 WCAG AA。
- 移动设备没有视口跳动，使用 `100dvh`。

## 阶段 8：自动化、视觉回归与预飞检查

### 文件

- 修改：`frontend-react/e2e/workflow.spec.ts`
- 新增：`frontend-react/e2e/ui-shell.spec.ts`
- 新增：`frontend-react/e2e/theme.spec.ts`
- 新增：`frontend-react/e2e/admin-pages.spec.ts`
- 修改：`frontend-react/playwright.config.ts`

### 实施

1. 增加深色和浅色主题的关键页面截图。
2. 覆盖 390px、768px 和 1440px。
3. 覆盖 Assistant 空状态、普通对话、活动工作流、等待审批、错误和历史恢复。
4. 覆盖管理员与普通用户的页面可见性和只读状态。
5. 验证键盘焦点、命令面板、抽屉和检查器。
6. 执行 design-taste-frontend 预飞检查，重点检查主题、颜色、圆角、图标、动效、移动端和空错误状态。
7. 运行 Lighthouse，记录性能、可访问性和 CLS。

### 发布门槛

- `npm run lint`
- `npx tsc --noEmit`
- `npm run build`
- `npm run test:e2e`
- 后端既有测试保持全绿。
- 3000 与 8000 端口在验收结束后停止监听。

## 阶段 9：Canva 最终视觉交付

### 目标

将真实实现转化为可编辑、可分享的 Canva 视觉规范，而不是让 Canva 生成器替代产品设计。

### 实施

1. 使用 Playwright 截取登录、Assistant、工作流中断、知识库、MCP、Agent 配置和 A2UI 的真实页面。
2. 将真实截图作为本地资产上传到 Canva，不发布到公共临时文件服务。
3. 生成品牌情绪板、主题色板、品牌标识、应用框架和组件规范页。
4. 将真实截图排入 Canva 视觉报告，避免占位联系方式、假数据、乱码和模板插画。
5. 向用户展示 Canva 预览并取得保存确认。
6. 保存后返回可编辑 Canva 链接。

## 建议提交拆分

1. `feat: 建立观心识流主题与品牌基础`
2. `feat: 重构应用框架与全局导航`
3. `refactor: 统一系统 Phosphor 图标体系`
4. `feat: 重构 Assistant 会话主舞台`
5. `feat: 实现工作流轨迹与状态控制台`
6. `feat: 重设计能力中心与系统配置页面`
7. `feat: 重设计登录与品牌动效`
8. `test: 补充主题响应式与关键交互验收`
9. `docs: 更新观心识流 UI 文档与 Canva 交付`
