---
id: a2ui
type: module-design
title: A2UI 声明式组件契约
status: draft
parent: architecture
---

# A2UI 声明式组件契约

## 职责

定义后端可以返回给前端的五类声明式 UI 卡片及其 Schema，负责校验、模板化生成与工具结果到卡片的映射；前端只按 Schema 渲染，不理解业务。

## 边界

- 组件目录是**契约**，不是样式实现：颜色、间距、主题全部属于前端。
- 不承载业务授权与副作用；卡片提交只是把值回传给工作流或 Agent，真正执行仍走 `workflows`。
- 只支持目录内的五种类型，未知类型校验失败。

## 契约

**五种组件**：`form_card`（输入表单，字段支持 input / select / textarea / number / switch）、`info_card`（键值对信息）、`list_card`（列表）、`confirm_card`（确认）、`chart_card`（图表数据，前端用 Recharts 绘制）。每类声明 `props_schema` 与 display_name。

**校验**：`validate_schema` 在入库与预览两处执行，脏 Schema 不进入消息。

**生成路径**：① `render_for_agent(template, data)` 用预定义模板把工具结果映射成卡片；② `render_dynamic(component_type, title, props)` 供 Agent 直接指定；③ 工具结果自动生成（如 `skill__query_users` 的统计看板由前端专项渲染，不走 A2UI）。

**接口**：`GET /api/a2ui/catalog`、`/catalog/{type}`、`/templates`，`POST /api/a2ui/preview` 接收 `{schema}` 返回校验结果，供管理页调试。

**持久化**：A2UI Schema 随消息存入 `conversation_messages.a2ui_schemas_json`，历史恢复与实时流渲染同源。

## 已知限制

- 卡片交互目前只回传表单值与确认结论，不支持自定义回调链。
- schema 没有版本号；改字段需同时改前端渲染器。
