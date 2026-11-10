---
id: skills
type: module-design
title: Skill 注册与执行
status: draft
parent: architecture
depends-on:
  - platform-core
---

# Skill 注册与执行

## 职责

定义「一个有名字、有参数契约、有返回结构的业务动作」，把内置 Skill 注册成模型可调用的工具，并在执行时做参数校验与角色限制。

## 边界

- 只负责注册、校验、执行编排；工具是否对某用户可见由 `tool-authorization` 决定，不在这里判断业务授权。
- 不直接面向 HTTP 协议：Skill 结果由 Agent 或工作流使用，前端只看工具结果与 A2UI 投影。
- 不做 Skill 版本管理、多版本共存或热插拔。

## 契约

**元数据**：`SkillMetadata` 声明 name、display_name、description、分类与参数（type、description、required、default、options）。参数校验失败返回明确错误串，不抛异常给模型。

**执行**：`SkillExecutor.execute(name, params, context)` 统一处理「未注册 / 角色不足 / 参数非法 / 执行异常」四种失败，返回 `SkillResult(success, data|error)`；同步实现放线程池执行并带 30 秒超时。`execute_chain` 为线性 DAG，任一步失败即停止。

**内置技能**：文本摘要、数据分析，以及管理型 `create_user` / `update_user` / `delete_user` / `query_users` / `export_data` / `system_diagnosis`。`ADMIN_ONLY_SKILLS` 是唯一的管理员名单，API 列表、Agent 工具目录、工作流目录、执行器四处共用。

**对外命名**：模型可见工具名为 `skill__{name}`，入参 Schema 由元数据生成；结果原样进入工具消息，`query_users` 的成功结果另由前端渲染成统计看板（见 `spec-users-dashboard`）。

**数据位置**：管理型 Skill 的业务记录保存在 `backend/data/users.json`（整文件 JSON 读写 + 进程内锁，非原子替换），与登录账号来源相互独立。

## 已知限制

- 技能参数只支持标量、数组与对象的基础类型，不支持嵌套联合或跨字段约束。
- `users.json` 是演示数据：写入直接覆盖原文件，进程崩溃或并发多进程写入可能丢记录。
