
> **规格状态**：本文是设计决策记录，**不是权威契约**。现行实现的权威契约在
> [`docs/specs/`](../../specs/)（spec-graph）；改动行为时以那里为准。

# 观心 v2 安全与工程收口设计

日期：2026-11-10
状态：待评审
基线：`feat/langchain-native-agent`（`e8e0b5a` + 在制品两个 commit）

## 背景

对观心 v2 做了一轮全栈工程评审（后端核心 / Agent 运行时 / 数据安全层 / 前端 / CI 五个方向并行深挖，结论均经代码与实测验证）。结论是：

- **作为 AI 辅助生成的稳定演示基线**，工程水位明显高于同类：规格驱动、边界诚实、176 条 pytest 全绿、CI 跑 lint+typecheck+build+Playwright、研究引用链可审计。
- **作为可交付软件**，存在 4 个可被低权限用户直接利用的洞，以及 3 处让「写操作只有一条路」这条核心承诺失效的授权漂移。

本设计把评审结论转成可执行、可回滚、可验证的收口工作。

**验收标准：内部演示 / 交付合作方看。** 即：安全底线必须修死；授权一致性必须与 spec 对齐；不追生产级审计日志、限流、密钥轮换等能力。

## 非目标

- 不做生产部署形态（高可用、横向扩展、多 worker 调度）——README 已明确排除。
- 不做账号体系生产化——登录账号与 API Key 仍是进程内预设数据。
- 不引入远程 MCP SSE、云端 MCP、条件分支工作流、并行 DAG。
- 不统一 HTTP 状态码语义（见「已接受的技术债」#3）。
- 不为 MCP Server 配置做数据库持久化（见决策 D2）。

---

## 分支与提交策略

### 基线修正

评审后确认：`main` 落后 `feat/langchain-native-agent` **4 个提交**，差 125 文件 / +10,234 / −10,615。整个 LangChain 原生迁移（`c96e478`）只存在于 feature 分支上。

因此**修复分支必须从 `feat/langchain-native-agent` 派生，而不是从 `main`**。从 main 派生会丢掉全部迁移。

### 提交序列

```
feat/langchain-native-agent
  ├─ e8e0b5a  (既有 HEAD)
  ├─ WIP-1    feat: 用户统计看板（skill__query_users + 前端看板 + E2E）
  ├─ WIP-2    docs: 将规格迁入 docs/specs spec-graph（11 份模块 spec）
  └─ harden/security-authorization-hardening   ← 新分支，从上面派生
```

WIP 两个 commit 的拆分依据：

- `WIP-1` = 代码与测试：`backend/app/services/user_store.py`、`backend/app/skills/builtins/{create_user,query_users}.py`、`backend/app/agent/deep_agent.py`、`backend/tests/test_user_statistics.py`、`frontend-react/src/components/agent/users-dashboard.tsx`、`frontend-react/src/components/agent/thread.tsx`、`frontend-react/e2e/users-dashboard-check.spec.ts`、`backend/app/seed/data.py`
- `WIP-2` = 文档：`docs/specs/**`（新建）、`docs/superpowers/specs/*.md` 的 frontmatter 迁移、`docs/architecture.md`、`docs/chroma-design-review.md`

先拆分再开分支，保证安全修复的 diff 里不混功能改动，回滚粒度以 commit 为单位。

### 仓库卫生（并入 W0）

`tmp/pdfs/agent-evolution-0907/` 下的 PNG / PDF / `build.py` 已被 git 跟踪（约 1.5 MB 二进制）。移除跟踪并补 `.gitignore` 的 `tmp/` 规则。

---

## 波次

| 波 | 内容 | 门禁 |
|---|---|---|
| W0 | 收口在制品 + 仓库卫生 | pytest / tsc / eslint / e2e 全绿 |
| W1 | 安全阻断 B1–B4 | 4 条新 pytest |
| W2 | 授权一致性 B5–B7 | 2 个新 pytest 文件 + spec 同步 |
| W3 | 运行时可靠性 B8–B10 | 事件写入量断言 + e2e |
| W4 | 契约与一致性收口 | typecheck / build / 死代码 grep = 0 |
| W5 | 自动化补齐 | CI 全绿 |

每波一个（或一组）commit，波间可独立回滚。

---

## W1 · 安全阻断

### B1 · 默认 JWT 密钥改为启动 fail-fast

**问题**：`config.py:31` 硬编码 `secret_key = "guanxin-v2-dev-secret-key-change-in-production"`，`.env.example:11` 交付同一值，lifespan 从不校验。实测可伪造 `admin-001/tenant-a` 的管理员令牌并通过 `decode_access_token`。这违反 AGENTS.md「Token 绝不硬编码」。

**方案**：新增 `app/core/secret.py`。

```python
DEFAULT_SECRET_KEY = "guanxin-v2-dev-secret-key-change-in-production"

def resolve_secret_key() -> str:
    """按 环境变量 → 持久化文件 → 随机生成 的顺序解析签名密钥。"""
```

优先级：

1. `settings.secret_key` 非空且 != 默认值 → 直接使用（运维显式配置）
2. 否则读 `data/.secret_key`（`<data_dir>/.secret_key`，权限 0600）
3. 仍无 → `secrets.token_urlsafe(48)` 生成，写入该文件（原子写：`tmp` + `os.replace`）

**内置默认值在任何环境都不会被真正用于签名**——它一律被当作「未配置」处理。development / test 只是不因此 fail-fast，实际签名密钥仍是随机生成的那一把。

**启动校验**（`app/main.py` lifespan 调用 `ensure_secret_key()`）：

- `settings.app_env` ∈ {`development`, `test`} → 允许继续启动，只打一条 WARNING
- 否则若显式配置为内置默认值 → **抛异常拒绝启动**，错误信息不含密钥本身
- 否则若显式配置的密钥短于 32 字符 → **抛异常拒绝启动**

`.env.example` 的 `SECRET_KEY=` 留空，注释说明：留空则自动生成并持久化到 `data/.secret_key`。

**改动点**：`app/core/secret.py`（新）、`app/core/security.py`、`app/config.py`、`app/main.py`、`backend/.env.example`

**验证**：新增 `tests/test_secret_key.py`

- 非 development 环境 + 默认密钥 → lifespan 启动被拒（`pytest.raises`）
- development 环境 → 启动成功且签发/校验令牌可用
- 连续两次 `resolve_secret_key()` 返回同一值（持久化生效）

### B2 · MCP Server 注册表加 tenant 维度

**问题**：`app/mcp/server.py` 的 `MCPServerManager._servers` 是进程级全局字典，无 tenant 字段。

- `register_server`（`:52`）由任意租户 admin 调用 → 写入全局表；`command`/`args` 被 `app/mcp/client.py:45` 真正 exec
- `unregister_server`（`:74-88`）只校验「调用者自己租户的 agent 配置里有没有它」，却删除全局条目 → tenant-b 的 admin 可以删掉 tenant-a 的 `weather`（其默认 `mcp_servers=["weather"]`）

**方案**（决策 D2：进程内加 tenant 维度，不落库）：

```python
class MCPServerManager:
    def __init__(self) -> None:
        self._servers: Dict[Tuple[str, str], dict] = {}   # (tenant_id, name) -> config

    def register_server(self, tenant_id: str, name: str, ...) -> dict
    def unregister_server(self, tenant_id: str, name: str) -> bool
    def get_server(self, tenant_id: str, name: str) -> Optional[dict]
    def list_servers(self, tenant_id: str) -> List[dict]
```

所有调用点补 `user.tenant_id`：`app/api/mcp.py` 的 register / unregister / list / connect / policy / call-tool。

`init_default_servers(tenant_id)`：seed 时为每个预设租户各注册一份 `weather`（`app/seed/init_data.py` 已有 tenant 列表）。

**保持现状的部分**：配置仍不跨重启保留（现状如此，README 已声明 MCP 为本地 stdio 连接）。此项列为已知技术债 #4。

**改动点**：`app/mcp/server.py`、`app/api/mcp.py`、`app/seed/init_data.py`、`app/agent/tool_catalog.py`（读 server 定义处）

**验证**：新增 `tests/test_mcp_tenant_isolation.py`

- tenant-b admin 注册的 server 不出现在 tenant-a 的列表里
- tenant-b admin 删除 tenant-a 的 `weather` → 404，且 tenant-a 的 agent 仍能拿到该工具
- tenant-b 的 agent 无法执行 tenant-a 注册的 MCP 工具

### B3 · MCP Server 列表不再向非 admin 泄露 env 与命令行

**问题**：`app/api/mcp.py:23-42` 的 `list_servers` 依赖 `get_current_user`（非 admin），但响应体是 `{**server, ...}`，而 `server` 含 `env`（MCP Server 的环境变量，通常是 API Key）与 `command` / `args`（后端解释器绝对路径）。实测 tenant-a 普通用户与 tenant-b admin 都能读到 `sk-super-secret-value`。

**方案**：按角色裁剪字段。

- admin：`env` 只返回 **key 名单**（`env_keys: ["OPENAI_API_KEY"]`），不返回值；`command` / `args` 保留（admin 需要诊断连接）
- 非 admin：只返回 `name` / `description` / `registered` / `runtime_status` / `agent_enabled`，**不含** `env` / `env_keys` / `command` / `args`

无论角色，`env` 的**值**都不出现在响应里（当前连 admin 都拿不到值，这是对的——值只在进程内用于 spawn 子进程）。

**改动点**：`app/api/mcp.py`

**验证**：新增断言——非 admin 响应体序列化后不含 env 值、不含解释器路径。

### B4 · 上传接口启用 max_upload_size_mb

**问题**：`app/api/knowledge.py:29` `content = await file.read()` 一次性把整个文件读进内存。`settings.max_upload_size_mb`（`config.py:56`）**全仓无读取方**——典型的「配置声明了但不执行」。

**方案**：

1. 预检 `file.size`（multipart 解析器已知长度时 → 直接 413，不读 body）
2. 分块读：`while chunk := await file.read(1 MiB)`，累计字节数超限 → 抛 `HTTPException(413)`
3. 超限时确保不落盘（解析发生在 `knowledge_service.upload_document` 内，校验在调用前完成）
4. 错误信息不回显限额以内的路径或内部细节

峰值内存因此被 `max_upload_size_mb` 硬性封顶，不再随请求体大小无限增长。

`max_upload_size_mb` 从死配置变为真正被读取的配置。

**改动点**：`app/api/knowledge.py`、`app/services/knowledge_service.py`

**验证**：新增断言——超限上传返回 413 且 `uploads/` 下无残留文件；限额内正常入库。

---

## W2 · 授权一致性

### B5 · 工作流与 Agent 共用同一份工具目录构建器

**问题**：Agent 链路（`app/agent/tool_catalog.py`）查 `mcp_tool_policies`，`enabled=False` 会跳过；工作流链路（`app/workflows/catalog.py`）**不查**，直接把所有 `get_tool_definitions()` 收进来。实测策略置 `enabled=False` 后，Agent 目录 `['kb_retrieval']`，工作流目录仍是 `['kb_retrieval', 'mcp__weather__get_weather']`。

而 `app/api/langchain.py` 的放行判断用的正是**工作流**目录 —— 管理员亲手关掉的开关，对唯一需要人工审批的路径是空操作。

**方案**：可见性与风险等级只有一份实现——`app.agent.tool_catalog.discover_tool_specs`。Agent 目录与工作流目录都从它派生：

- 两边统一按 `mcp_tool_policies` 过滤 `enabled`
- `effect` → `risk` 映射统一：`read` → `read`，`write` → `write`，其余 → `unknown`
- `app/workflows/catalog.py::execute_tool` 在 `mcp__` 分支**再查一次** `enabled`（纵深防御）
- `kb_retrieval` 是唯一例外：工作流侧额外暴露 `top_k`，与 Agent 侧的工具签名本就不同，各自构造

**改动点**：`app/agent/tool_catalog.py`、`app/workflows/catalog.py`

**验证**：新增断言——策略 `enabled=False` 后，Agent 目录与工作流目录**都不含**该工具；工作流执行被拒。

### B6 · Skill effect 必填 + 风险判定 fail-closed

**问题**：两个风险分类器方向相反。

```python
# app/workflows/catalog.py:82  —— fail-open
risk = "write" if metadata.effect == "write" else "read"
```

任何非 `"write"` 字面值（含 `"unknown"`、`None`、拼写错误）都变成 `read` → 无人工审批自动执行。而 `app/agent/tool_catalog.py:172` 是 fail-closed（只认 `read`/`write`，其余 `unknown`）。

`app/models/skill.py:61` 的 `effect: str = "read"` 无校验且有宽松默认值。8 个 builtin 中只有 `create_user` / `update_user` / `delete_user` 声明了 `write`；`export_data` / `system_diagnosis` / `query_users` / `data_analysis` / `text_summary` 全部继承默认 `read`。

**后果**：下一个新 Skill 只要忘了声明 `effect`，就会同时被 Agent 与工作流引擎**免审**执行。这直接违反 `docs/specs/goal-and-requirements.md` 的「写操作只有一条路」。

**方案**：

1. `SkillMetadata.effect: Literal["read", "write", "unknown"]`，**必填、无默认值**
2. 注册时校验：effect 不在三值内 → 拒绝注册该 Skill 并记日志（不静默丢弃）
3. 8 个 builtin 逐个显式标注：

   | Skill | effect | 依据 |
   |---|---|---|
   | `create_user` | `write` | 创建业务记录 |
   | `update_user` | `write` | 修改业务记录 |
   | `delete_user` | `write` | 删除业务记录 |
   | `query_users` | `read` | 只读查询 |
   | `data_analysis` | `read` | 只读分析 |
   | `text_summary` | `read` | 纯函数 |
   | `export_data` | `read` | 导出即只读快照，不改状态 |
   | `system_diagnosis` | `read` | 只读诊断 |

4. 统一判定为 fail-closed：**只有显式 `effect == "read"` 才自动执行**；`write` 与 `unknown` 一律进入可审批的持久化工作流
5. `app/agent/tools.py:21` 与 `app/skills/executor.py:14` 重复的 `ADMIN_ONLY_SKILLS` 合并为一份（放在 `SkillMetadata` 旁）

**改动点**：`app/models/skill.py`、`app/skills/registry.py`、`app/skills/builtins/*.py`（8 个）、`app/agent/tool_catalog.py`、`app/workflows/catalog.py`、`app/agent/tools.py`、`app/skills/executor.py`

**验证**：新增断言——effect 未声明 / 值为 `unknown` 的 Skill **不得**出现在 runtime_tools（只读自动执行集合）中，必须走审批。

### B7 · 移除正则意图旁路

**问题**：`app/workflows/intent.py:40-45` 的匹配式无问句守卫，实测：

```
'如何删除用户'         -> 'single_delete'
'怎么删除用户？'        -> 'single_delete'
'解释一下删除用户的流程'   -> 'single_delete'
```

然后 `app/agent/thread_service.py:99-107` **完全绕过模型**（无模型调用、无回答），直接起工作流 → 用户拿到的是一张「确认执行：删除用户」的审批卡。最危险的措辞配上最容易误点的卡片。同时，一大类普通问句永远到不了模型。

**方案**（决策 D3：移除旁路，只走工具）：

- `thread_service._execute` 删除 `detect_workflow_intent` 分支，不再有「无模型直起工作流」的路径；Agent 运行一律先过模型
- 写操作统一经 `request_business_workflow` 工具发起 —— **该工具已存在**（`app/agent/deep_agent.py` 的 prompt 里已声明），入口无需新建
- 问句守卫下沉到**意图分类层**（`app/workflows/intent.py::looks_like_question` + `planner.py::detect_workflow_intent`）：问句一律不产生变更类意图。这个判定保护所有入口——Agent 工具、工作流引擎与外部调用方
- `deep_agent.py` 的 prompt 明确：问句只解释流程与所需参数，不发起变更审批

**为什么把问句守卫放在分类层而不是只删旁路**：意图分类器仍被 `request_business_workflow` 用来选择计划形态（确定性单步 vs LLM 规划）。如果只删旁路而不加守卫，模型把「如何删除用户」当作 goal 传进工具时，确定性计划仍会指向 `skill__delete_user`。

**行为变化（需在 demo 手册中体现）**：「如何删除用户」现在会得到解释性回答，而不是一张删除审批卡；「删除用户 user42」仍会经模型规划后进入审批。

**e2e 与 CI 调整**：原工作流浏览器用例依赖旁路（CI 不配 LLM Key 也能跑通）。移除旁路后，用例改为在**确定性模型 fixture** 下运行——fixture 让模型真的发出 `request_business_workflow` 工具调用，因此覆盖的是完整的 agent → 工具 → 审批链路，而不是绕过模型。CI 相应把该用例并入 fixture 那一轮。

**改动点**：`app/agent/thread_service.py`、`app/workflows/intent.py`、`app/workflows/planner.py`、`app/agent/deep_agent.py`、`backend/tests/native_app.py`、`frontend-react/e2e/workflow.spec.ts`、`.github/workflows/ci.yml`

**验证**：新增断言——问句不产生 `workflow_runs` 记录；祈使句经模型产生记录。

---

## W3 · 运行时可靠性

### B8 · 事件写入改走 aiosqlite 共享连接

**问题**：`app/agent/thread_service.py:143` 在 `async for` 循环里**同步**调用 `runs.append_event(run, event)`；`app/services/agent_run_store.py:56-63` 每次事件开一个新连接、`BEGIN IMMEDIATE`、两条语句、commit、close。

v3 协议**每个模型 chunk 发一个 `content-delta`**（已核对安装的 `langchain-core/chat_models.py:717-723` 的 `achunks_to_events`，且 `ChatOpenAI(streaming=True)` 见 `app/agent/llm.py:33`）。实测 `append_event` ≈ 0.62 ms/次 → ~1600 events/s 上限，**全部发生在事件循环内**。1k token 的回答 ≈ 1k 次事务 ≈ 阻塞事件循环 0.6s，期间 SSE 轮询、`/state`、其他租户的 run 全部排队。

**方案**（决策 D1：异步写）：

1. `app/services/agent_run_store.py` 的写入函数改为 async，底层用 `asyncio.to_thread` 把提交挪出事件循环，**复用 `app/core/sqlite.py` 的既有纪律**（WAL、`busy_timeout=5000`、`BEGIN IMMEDIATE`、外键、参数化 SQL）——那套纪律已经被 176 条测试覆盖
2. **`append_event` 合并为单条 INSERT**：`seq` 与 `event_id` 在 `read_events` 时补齐，写入不再需要「先插空行、再 UPDATE 回填 payload」的两步写。每条事件的写入量减半
3. `thread_service` / `api/langchain.py` / `api/research.py` / `main.py` 的调用点相应 `await`

**为什么不用共享 aiosqlite 连接**（实施时对原方案的调整）：`aiosqlite` 的每个 Connection 绑定一个后台线程，沿用「每次操作新开连接」会变成每次操作 spawn 一个线程；而共享单个连接需要额外引入连接生命周期与跨事件循环的锁管理——而 SQLite 本身就是单写者，共享连接并不带来吞吐收益。`asyncio.to_thread` 拿到的是完全相同的性质（写不阻塞事件循环），却没有生命周期与跨循环隐患。

**读路径保持同步 sqlite3**：读耗时 <1ms，且全量 async 化的爆炸半径过大。WAL 模式下多连接安全。

**已知遗留**（本方案**不**解决，见「已接受的技术债」#1、#2）：

- 每 token 仍是一次事务（fsync 次数未降）
- `values` 事件仍内嵌全量消息列表 → 事件表体积 O(n²)

**改动点**：`app/services/agent_run_store.py`、`app/agent/thread_service.py`、`app/api/langchain.py`、`app/api/research.py`、`app/main.py`

**验证**：`tests/test_agent_event_store.py`（5 条）

- `loop.call_soon` 排的回调能在写入期间执行 → 确定性地证明事件循环没有被阻塞
- 每条事件只占一行，落库 payload 不含 `seq` / `event_id`
- 读取时补齐单调递增的 `seq` 与稳定的 `event_id`
- 游标重放语义不变（增量读取与全量一致）
- 终止事件仍按既有约定写入

### B9 · 发送失败时恢复草稿与附件

**问题**：`frontend-react/src/components/agent/thread.tsx` 先 `setDraft("")` 再 `await stream.submit(...)`，catch 里 `setDraft(text)` 恢复。

但 `useStream().submit()` **不 reject** —— 已读安装的 `@langchain/langgraph-sdk@1.10.2` 源码 `dist/stream/submit-coordinator.js`：

```js
} catch (error) {
    if (!abort.signal.aborted) settleEvent = "failed";
    reportError(error);          // → rootStore.error + options.onError，不 rethrow
}
```

所有失败（409「请先处理或取消当前工作流」、422、5xx、后端宕机）都被吞成 `rootStore.error`，`await` 正常 resolve → **catch 不执行 → 草稿和附件都没了**，用户只看到一条错误横幅。

**方案**：

```js
const failedRef = { current: false }
await stream.submit(payload, {
  onError: (error) => {
    failedRef.current = true
    setDraft(text)
    setAttachment(attachment)
    setActionError(...)
  },
})
if (!failedRef.current) { setDraft(""); setAttachment(null) }
```

SDK 的 `onError` 在 dispatch-failure 与 terminal-failure 两条路径都会调用。**`failedRef` 是必要的**：SDK 正常 resolve 后无条件清空草稿，会把 `onError` 刚恢复的内容又抹掉——只有「命令确实被接受」才清空。

**改动点**：`frontend-react/src/components/agent/thread.tsx`

**验证**：e2e 断言失败后输入框内容仍在；W5 补纯函数用例。

### B10 · 统一前端错误态 + 补 error boundary

**问题**：五个 store 的失败策略各不相同，同一类故障有五种用户可见结果。

| 位置 | 现状 | 用户看到 |
|---|---|---|
| `stores/knowledge.ts:25-35` | throw | **「知识库还是空的」** ← 网络故障被说成没数据 |
| `stores/skill.ts:22-32` | throw | 「暂无可用 Skill」 |
| `stores/mcp.ts:39-48` | `catch {}` 静默 | 「暂无活跃连接」 |
| `stores/a2ui.ts:22-42` | `catch {}` 静默 | 永久「正在读取目录」 |
| `stores/agent.ts:27-49` | `finally` 无 catch | **永久转圈**（`agent/page.tsx:173`） |

App Router 树里没有任何 `error.tsx` / `global-error.tsx` / `not-found.tsx` / `loading.tsx` —— 一个坏响应会让整个工作台变成 Next 默认错误页。

**方案**：

1. 每个 store 增加 `error: string | null`，成功时清空、失败时写入（`src/lib/api/errors.ts` 提供统一的 `describeError`）
2. 统一空态判定规则：**`data.length === 0 && !error && !loading` 才显示空态**；有 error 则显示错误态 + 重试按钮（新增 `components/layout/error-state.tsx`）
3. 新增 `src/app/(main)/error.tsx`（client component，`reset()` 重试）与 `src/app/global-error.tsx`
4. **401 策略统一**：新增 `handleUnauthorized()`（清 token + 跳登录页），`lib/api/client.ts` 的 axios 拦截器与 `thread.tsx` 的 `authorizedFetch` 共用；登录页自身返回 401 时不再跳转（避免刷新循环）
5. `stores/auth.ts::fetchMe()` 此前是**死代码**（零调用点）→ 在 `AuthGuard` 挂载时调用一次，使过期 token 在用户发起 run 之前就被发现

**顺带修掉会话切换竞态**（同属一类问题）：`assistant.tsx` 的 `selectConversation` 此前没有请求序号保护，两次快速点击会让**先发后到的旧响应覆盖新选择**（工作区显示的会话与用户最后点击的不一致，`localStorage` 也被写错）。现在用 `selectRequestRef` 序号保护，只有最后一次请求的结果会被应用。

**改动点**：`frontend-react/src/lib/stores/*.ts`、`frontend-react/src/lib/api/{client,errors}.ts`、`frontend-react/src/components/agent/thread.tsx`、`frontend-react/src/components/layout/error-state.tsx`（新）、`frontend-react/src/app/(main)/error.tsx`（新）、`frontend-react/src/app/global-error.tsx`（新）、`frontend-react/src/components/auth/AuthGuard.tsx`、`frontend-react/src/app/assistant.tsx`、各管理页空态判定

**验证**：Playwright 断言后端返回 500 时页面显示错误态而非空态。

### W3 附带项 · 阻塞事件循环与无超时

评审中同批发现、同一波次内一并修（改动小、风险低）：

- `app/api/skill.py:54-66`：`ThreadPoolExecutor` + `future.result(timeout=30)` 阻塞事件循环；且 `with` 退出时 `shutdown(wait=True)` 会继续等任务跑完 → 超时形同虚设（实测 0.51s 抛错、2.01s 才退出）。改为 `await asyncio.to_thread(...)` + 内部 `asyncio.wait_for`
- `app/mcp/client.py`：`session.initialize()` / `session.call_tool()` 均无超时 → 挂死的 MCP Server 可永久占住请求。加 `read_timeout_seconds` + 外层 `asyncio.timeout`（超时按 tool error 返回）
- `app/mcp/client.py:160`：失败的工具调用在 Agent 路径被当作 `success: true` 传给模型 → `is_error` 必须在 Agent 路径也转成显式失败

---

## W4 · 契约与一致性收口

### 前端类型边界收紧

**问题**：`src/types/index.ts:1-6` 的 `ApiResponse<T>` 泛型是装饰性的 —— `client.get(url)` 返回 `Promise<AxiosResponse<any>>`，`any` 实例化让 TypeScript 认为它可赋给任何类型，编译器零校验。实测 `client.get("/x")` 可赋给 `Promise<ApiResponse<{a:number}>>`。

**方案**：

```ts
type ApiClient = {
  get<T>(url: string, config?: AxiosRequestConfig): Promise<ApiResponse<T>>
  post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<ApiResponse<T>>
  // …
}
```

让 `client.get<T>(...)` 真正被检查。同时对驱动渲染的两个 envelope（`WorkflowData` / `ResearchData`）在 store 边界做**运行时校验**（引入 `zod`，1 个依赖），避免 `null` payload 变成 `null` state。

### A2UI 预览走后端校验

**问题**：`src/app/(main)/a2ui/page.tsx:152-160` 的「应用 Schema」按钮直接 `JSON.parse` 就 `setCurrentSchema`，非法 schema 静默回落 `InfoCard` 并给绿色 toast。后端**已经有**校验器 `POST /api/a2ui/preview`（`app/api/a2ui.py:51-60`），前端也已有 client（`lib/api/a2ui.ts:26-28`）但从未调用。页面还重复声明了后端 `app/a2ui/templates.py` 的模板 fixture。

**方案**：调用 `a2uiApi.previewSchema(parsed)`，仅在 `res.code === 0` 时应用；删除前端重复的模板 fixture，改用后端 `/a2ui/templates` 与 `/a2ui/render`。

### 用户看板改为结构化渲染

**问题**：模型 ↔ UI 的看板协议是一句 prompt 指令 + 一个正则（`deep_agent.py:146` 的「正文以 `[看板]` 开头」↔ `users-dashboard.tsx:90` 的 `/^\s*\[看板\]\s*/`）。模型不写标记 → 看板不渲染；写在句中 → 正文被静默吞掉。而**工具结果里本来就有 `statistics` / `filters` 结构化数据**。

**方案**：看板改为**直接用 `skill__query_users` 的工具结果渲染**；`[看板]` 标记降级为兜底（结构化数据缺失时才用散文解析）。服务端在 `_persist_transcript` 里剥离标记，UI 不再需要猜。

### 死代码与依赖清理

**后端**（评审已 grep 确认零引用）：

- `app/agent/prompts.py`：`USER_SYSTEM_PROMPT_BACKUP`、`INTENT_CLASSIFICATION_PROMPT`、`CONFIRM_MODE_PROMPT_SUFFIX`、`AI_ELEMENTS_TOOLS_GUIDE`、`build_system_prompt`
- `app/agent/tools.py`：`get_tools`、`get_enabled_tools`、`skill_execute_tool_factory`、`_create_mcp_langchain_tool`（已在 W1 一并删除——它们依赖的 MCP 内部契约已变更，留着会变成坏路径）
- `app/agent/tool_catalog.py::catalog_prompt`
- `app/core/tenant.py::clear_tenant_context`
- `app/skills/base.py::as_langchain_tool`
- `app/core/exceptions.py`：**删除**（实施时对原方案的调整）。原方案是「启用而非删除」，但它构成第三套无人使用的异常机制，而 `app/core/responses.py` 的 `success()` / `error()` 与 FastAPI 的 `HTTPException` 已覆盖全部场景；HTTP 语义按决策保持现状，没有留给它的缺口。启用只会增加噪音。
- `app/services/research_store.py`：**保留**。评审称它是死写路径，但实际不是——旧研究归档的「转入原生任务」功能靠它读取，测试也用它播种归档数据。
- `app/agent/llm.py::_create_llm` → 改名为 `create_llm`（私有约定却被另外两个模块导入）；同时修掉它吞掉真实错误的问题：此前任何初始化异常都被转成「请先配置 OPENAI_API_KEY」，401、地址写错、模型名无效全被误诊成同一个问题且无日志。现在区分「未配置密钥」（返回 None）与「初始化失败」（记日志并抛 `LLMConfigurationError`）。

**前端**：

- 10 个未使用的运行时依赖：`dayjs`、`nanoid`、`shiki`、`tw-shimmer`、`streamdown`（+ `@streamdown/{cjk,code,math,mermaid}`）、`use-stick-to-bottom`、`radix-ui`（统一包，代码用的是分包）、`rehype-highlight`、`highlight.js`
- 7 个从未 import 的 `components/ui/*`：`alert`、`button-group`、`checkbox`、`hover-card`、`input-group`、`popover`、`spinner`（其中 3 个是这些 radix 分包唯一的安装理由）
- `src/lib/design-tokens.ts` **接线而非删除**：其值目前硬编码在标记里（`railWidth:72` → `primary-rail.tsx:30`；`secondaryWidth:264` → `assistant.tsx:54`；`toolbarHeight:56` → `context-toolbar.tsx:33`；`inspectorWidth:320` → `context-panel.tsx:27`），改为引用 token
- 空目录 `src/app/(main)/chat/`（`src/app/page.tsx` 先跳 `/chat` 再被永久重定向到 `/assistant`，两次往返）

**规格双源收敛**：`docs/specs/`（spec-graph，11 份模块 spec，带 frontmatter）作为**唯一事实源**；`docs/superpowers/specs/` 只保留按日期归档的设计决策记录，并在文件头注明「非权威，被 `docs/specs/` 取代」。

---

## W5 · 自动化补齐

**后端 pytest**（新增）：

| 文件 | 覆盖 |
|---|---|
| `tests/test_secret_key.py` | B1 fail-fast、密钥持久化 |
| `tests/test_mcp_tenant_isolation.py` | B2 跨租户注册/删除/执行隔离 |
| `tests/test_mcp_server_disclosure.py` | B3 env 与命令行不外泄 |
| `tests/test_upload_limits.py` | B4 超限 413 且不落盘 |
| `tests/test_tool_authorization.py` | B5 禁用开关两条路径都生效、B6 fail-closed |
| `tests/test_workflow_intent.py` | B7 问句不建工作流 |
| `tests/test_agent_event_store.py` | B8 写入量与事件循环不阻塞 |

**前端单测**：引入 `vitest`（仅纯函数，不引入 jsdom / testing-library）。看板的解析与判定逻辑从组件里抽到 `src/components/agent/users-dashboard-data.ts`（否则测试会拖进 React + recharts），覆盖 `parseUsersResult` / `dashboardNumbers` / `stripDashboardMarker` / `isDashboardRestatement`（17 条表格用例）；消息组装与长度校验抽到 `compose.ts`（5 条）。接进 CI。

**Playwright 增补**：`e2e/authorization.spec.ts` 覆盖上传超限（e2e 后端把上限压到 1 MB）、MCP Server 跨租户隔离、env 值不外泄；`e2e/workflow.spec.ts` 增补「问句不建工作流」用例（确定性 fixture 下模型只回答不调工具，断言没有审批卡与工作流状态）。

**CI**：新增 `npm run test:unit` 步骤；fixture 那一轮包含工作流用例。

---

## 规格同步

按 spec-graph 规则「改动边界时同步更新拥有该边界的 spec」，本设计涉及以下 spec 更新：

| spec 文件 | 更新内容 | 对应波次 |
|---|---|---|
| `docs/specs/modules/platform-core.md` | 密钥解析与 fail-fast 规则；HTTP 状态码两套约定是**有意为之**；MCP 配置不跨重启保留 | W1 / W3 / W4 |
| `docs/specs/modules/mcp.md` | MCP Server 注册按租户隔离；非 admin 不可见 `env` 与命令行；工具调用有超时 | W1 / W3 |
| `docs/specs/modules/tool-authorization.md` | `effect` 必填 + fail-closed 判定；禁用开关在 Agent 与工作流两条路径都生效；写操作唯一入口是 `request_business_workflow` | W2 |
| `docs/specs/modules/agent-runtime.md` | 事件写入走 aiosqlite 共享连接；问句不触发工作流 | W2 / W3 |
| `docs/specs/modules/frontend-app.md` | 错误态统一规则与 error boundary；看板按工具结果结构化渲染；A2UI 预览走后端校验；令牌由 `design-tokens.ts` 统一 | W3 / W4 |
| `docs/specs/goal-and-requirements.md` | 「写操作只有一条路」的落地方式改为「唯一入口 = `request_business_workflow` 工具」，不再依赖模型侧正则路由 | W2 |

---

## 已接受的技术债

明确记录为「知道、暂不修」，避免下一轮重复评估：

1. **每 token 一次 fsync 事务**。aiosqlite 解决了「阻塞事件循环」，未解决「写入次数」。彻底解需要事件合并写（writer task + 批量 INSERT），属于独立重构。
2. **`values` 事件内嵌全量消息列表** → `agent_events` 体积 O(n²)。彻底解需要剥离持久化 payload，会影响重放语义，需单独设计。
3. **HTTP 状态码两套约定并存**：认证失败用 `200 + {"code": 4011}`，业务错误用真 `401/403/404/409`。前端 26 处依赖 `code === 0`；改真 401 会触发 axios 拦截器跳登录页。**保持现状，在 `docs/specs/modules/platform-core.md` 写明这是有意约定**，并同步启用 `app/core/exceptions.py` 的异常族（统一新增错误的表达方式），不再让下一个人误以为是疏漏。
4. **MCP Server 配置不跨重启保留**（进程内存储）。B2 修的是跨租户越权，持久化是独立收益项。
5. **API Key / JWT 无法吊销轮换**。演示级验收下接受。

---

## 验收

### 逐波门禁

- **W0**：`pytest -q` 全绿、`tsc --noEmit` 退出 0、`eslint .` 退出 0、`npm run test:e2e` 全绿
- **W1**：`tests/test_secret_key.py` / `test_mcp_tenant_isolation.py` / `test_mcp_server_disclosure.py` / `test_upload_limits.py` 全绿
- **W2**：`tests/test_tool_authorization.py` / `test_workflow_intent.py` 全绿；`docs/specs` 对应模块 spec 已更新（见「规格同步」表）
- **W3**：`tests/test_agent_event_store.py` 全绿（写入量不高于基线、事件循环不阻塞）；B9 / B10 的 Playwright 用例全绿
- **W4**：`tsc --noEmit` 退出 0、`next build` 成功、死代码 grep 命中数为 0、`package.json` 依赖与 `src/` 引用一致
- **W5**：CI 全绿（pytest + lint + typecheck + build + vitest + Playwright）

### 全局门禁

- `.github/workflows/ci.yml` 增加 `vitest run` 步骤
- README 的「本轮运行边界」「已知边界」两节同步更新（密钥策略、MCP 租户隔离、事件写入方式）
- `docs/demo-guide.md` 补充 B7 带来的交互变化（问句不再触发审批卡）

---

## 回滚

每个波次一个（或一组）commit，标签：

```
harden-w1-security      B1–B4
harden-w2-authorization B5–B7 + spec 同步
harden-w3-runtime       B8–B10 + 附带项
harden-w4-contract      契约收口 + 死代码清理
harden-w5-tests         自动化补齐
```

B8 涉及数据库写入路径，回滚时需确认 `agent_events` 表结构未变（本设计不改动该表结构，只改写入方式与语句条数）。
