---
id: platform-core
type: module-design
title: 平台核心：持久化、租户与认证
status: draft
parent: architecture
---

# 平台核心：持久化、租户与认证

## 职责

所有模块共用的底座：SQLite 业务库的连接与 schema 演进、LangGraph checkpointer、请求级租户上下文字、JWT / API Key 认证、统一响应与请求中间件。

## 边界

- **只有 core 层持有连接与客户端单例**：`app/core/sqlite.py`（业务库）、`app/core/database.py`（ChromaDB）、`app/core/checkpoints.py`（LangGraph saver）。业务模块经 store / service 访问，不自行打开裸连接或复制 pragma 配置。
- 本层不放业务规则：谁能看哪条会话、哪个工具可执行属于各业务模块与 `tool-authorization`。
- 前端、MCP 网关都不得绕过 HTTP API 直接触碰 SQLite / ChromaDB。

## 契约

**连接与事务**：每次操作新建连接，启用 WAL、`foreign_keys=ON`、`busy_timeout=5000`；写事务一律 `BEGIN IMMEDIATE`，让并发写者在 busy_timeout 内排队，而不是在锁升级时失败。

**Schema 演进**：`initialize_database()` 幂等执行 `SCHEMA_VERSION = 5` 的建表脚本，历史版本记录在 `schema_version`；破坏性变更以单独 migration 函数执行（v4 折叠重复的工作流快照消息，v5 只在系统提示仍等于旧默认值时升级）。

**租户上下文**：`set_tenant_context(tenant_id, user_id, user_role)` 写入 contextvars，由认证依赖在请求开始时设置。业务查询从上下文或显式参数取值，**永不信任请求体里的租户或用户**。

**认证**：JWT（HS256，载荷含 `sub` 与 `tenant_id`）或 `X-API-Key` 二选一。预设账号在启动时幂等初始化，密码用 bcrypt（截断到 72 字节）。管理端点叠加 `get_admin_user`。

**签名密钥**：按 `SECRET_KEY` 环境变量 → `<数据目录>/.secret_key` → 随机生成（0600 原子写）的顺序解析，进程内缓存保证同一进程始终用同一把。仓库里不携带任何可被公开利用的固定密钥——内置历史默认值一律视为「未配置」，在**任何**环境都不会被真正用于签名。非 development / test 环境下，若仍配置为内置默认值或密钥短于 32 字符，lifespan 拒绝启动。

**越权语义**：跨租户或跨用户的对象一律返回 404（不泄露存在性）；角色不足返回 403。

**响应契约**：普通业务端点统一 `{code, message, data}`；Agent 线程协议端点返回官方 SDK 要求的形状（`values` / `next` / 事件流），不使用 envelope。

**HTTP 状态码约定**（有意为之，不是疏漏）：认证失败返回 `200 + {code: 4011}`，其余业务错误使用真实的 `401 / 403 / 404 / 409 / 413 / 422`。前端统一按 `code` 判定成功与否，不按 HTTP 状态码。

**可观测性**：`RequestContextMiddleware` 为每个请求打 `X-Request-ID` 与 `X-Response-Time`。

**Checkpointer 生命周期**：进程内单例 `AsyncSqliteSaver`，`LANGGRAPH_STRICT_MSGPACK=true`；关闭时释放并重置工作流图；删除会话时同步删除对应 thread。

## 已知限制

- 账号与 API Key 是进程内预设数据，重启后需重新获取；`backend/data/users.json` 是管理型 Skill 的业务记录，不是登录来源。
- 单进程 Uvicorn 是设计前提，不提供多 worker 调度或分布式锁。
- `settings.agent_mode` 已无消费方（后端自报 `deepagents`），属遗留配置。
- MCP Server 配置同样是进程内数据，重启后需重新注册。
