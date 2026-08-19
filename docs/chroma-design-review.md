# ChromaDB 数据库设计架构评审报告

> 评审人：架构师 高见远
> 评审日期：2026-07-12
> 评审范围：guanxin-v2 后端 ChromaDB 相关全部代码
> 项目定位：Demo 级多租户 AI 助手系统（FastAPI + LangGraph + ChromaDB）

---

## 评审结论总览

| 维度 | 评级 | 一句话结论 |
|------|------|-----------|
| 设计决策合理性 | ✅ 合理 | 嵌入式 ChromaDB 完全匹配 Demo 定位，零部署成本是最大优势 |
| 多租户隔离 | ⚠️ 基本可用但有隐患 | collection-per-tenant 思路正确，但缺少输入校验和查询级 where 过滤 |
| 并发安全 | 🔴 有实质风险 | 同步阻塞调用直接跑在事件循环中，高并发下会卡死 |
| 数据一致性 | 🔴 双写不一致 | 内存 Store + ChromaDB 无事务保证，异常路径数据会漂移 |
| 距离转相似度 | ⚠️ 公式当前正确但脆弱 | 依赖隐式假设（L2 空间 + 归一化向量），未显式声明距离度量 |
| 异常处理 | 🔴 吞异常严重 | 多处 `except Exception: pass` 静默吞错，排障极难 |

**总体判断**：对于 Demo 级项目，这套设计"能跑"，架构选型决策是合理的。但在并发安全、数据一致性、异常处理三个方面存在实质风险，即使 Demo 演示中也可能暴露。建议按下方 P0/P1 分级修复。

---

## 1. 设计决策分析：为什么选择 ChromaDB 嵌入式模式？

### 1.1 决策复盘

架构文档（`docs/architecture.md` 决策 2）给出了四条理由：

| 理由 | 评审意见 |
|------|---------|
| 零部署成本（pip install 即用） | ✅ 完全成立。Demo 项目最大痛点是环境搭建，嵌入式模式省去 Docker/独立进程，`scripts/start.sh` 一键启动名副其实 |
| Python 原生，与 FastAPI 同进程，无网络开销 | ✅ 成立。百级文档检索延迟 < 50ms 的预期合理，同进程调用确实省去网络往返 |
| 通过 collection 命名实现多租户隔离 | ⚠️ 思路正确，但实现有缺陷（详见第 2 节） |
| Demo 数据量下性能足够 | ✅ 成立。ChromaDB 嵌入式在万级向量以内性能可接受 |

### 1.2 对项目定位的适配性

项目自我定位为 **"AI Agent 全栈 Demo 系统"**（见 `pyproject.toml` description）。在这个定位下：

- **优点**：选择嵌入式而非独立部署的 ChromaDB/Qdrant/Milvus 是正确的 trade-off。独立部署向量库对于 Demo 是过度设计，增加部署复杂度违背"一键启动"原则。
- **隐性代价**：嵌入式模式绑定了单进程架构。架构文档 D-3 已识别到这个风险（"ChromaDB 嵌入式模式在多进程下的并发安全性"），假设 MCP Server 进程通过 HTTP API 调用主服务检索。这个假设是合理的，但需要确保 MCP Server 代码中**不直接 import chromadb**，否则会触发 SQLite 多进程写锁冲突。

### 1.3 选型横向对比

| 方案 | 部署成本 | 多进程安全 | 适合 Demo？ |
|------|---------|-----------|------------|
| **ChromaDB 嵌入式（当前选择）** | 零 | ❌ 单进程 | ✅ 最佳 |
| ChromaDB Docker 模式 | 中 | ✅ | ⚠️ 过重 |
| Qdrant | 中 | ✅ | ⚠️ 过重 |
| FAISS + 自管 | 高（需自实现持久化） | ❌ | ❌ |
| SQLite-VSS | 低 | ❌ | ⚠️ 生态小 |

**结论**：选型决策合理，无需更改。

---

## 2. 多租户隔离方案评审

### 2.1 当前方案

```
collection 命名规则: tenant-{tenant_id}-kb
隔离手段: 每个租户一个独立 collection
查询时: 直接操作对应 collection，无 where 条件二次过滤
```

### 2.2 问题分析

#### 问题 2.2.1 [P1] tenant_id 未做输入校验，存在 collection 名称注入风险

`get_or_create_collection(tenant_id)` 直接拼接 `f"tenant-{tenant_id}-kb"`，如果 `tenant_id` 包含特殊字符（如 `a/../b`、空格、超长字符串），可能导致：
- collection 名称冲突（两个不同 tenant_id 拼出同名 collection）
- ChromaDB collection 名称限制（最长 63 字符，仅允许 `[a-zA-Z0-9_-]`）

**代码位置**：`database.py:41`
```python
collection_name = f"tenant-{tenant_id}-kb"  # 无校验
```

#### 问题 2.2.2 [P1] 查询缺少 where 条件二次过滤

当前检索完全依赖 collection 级隔离，`collection.query()` 不带 `where={"tenant_id": tenant_id}` 过滤。虽然 collection 级隔离在正常情况下已足够，但缺少防御性 where 过滤意味着：
- 如果因任何 bug（如 collection 名称碰撞）导致跨租户数据混入，检索会直接泄露
- 不符合"纵深防御"原则

**代码位置**：`retrieval_service.py:67-71`
```python
results = collection.query(
    query_embeddings=[query_embedding],
    n_results=min(top_k, collection.count()) if collection.count() > 0 else top_k,
    include=["documents", "metadatas", "distances"],
    # 缺少: where={"tenant_id": tenant_id}
)
```

#### 问题 2.2.3 [P2] list_collections() 不区分租户，泄露全局信息

`list_collections()` 返回所有 collection 名称，任何调用方都能看到所有租户的存在和数量。

**代码位置**：`database.py:62-65`

#### 问题 2.2.4 [P2] 文档与代码不一致

架构文档 `docs/architecture.md` 第 145 行和第 1643 行写的是 `tenant-{id}-kb-{name}`，但实际代码用的是 `tenant-{id}-kb`（无 `-{name}` 后缀）。文档还提到"所有查询带 tenant_id 过滤"，但代码中并未实现。

### 2.3 隔离方案总体评价

collection-per-tenant 的隔离粒度对于 Demo 是合适的——比"单 collection + metadata 过滤"更干净，比"database-per-tenant"更轻量。思路正确，但实现缺少防御性措施。

---

## 3. 并发安全评审

### 3.1 当前方案

```python
# database.py
_chroma_client: Optional[chromadb.PersistentClient] = None
_chroma_lock = threading.Lock()

def get_chroma_client():
    if _chroma_client is None:          # 第一次检查（无锁）
        with _chroma_lock:               # 加锁
            if _chroma_client is None:   # 第二次检查（有锁）
                _chroma_client = chromadb.PersistentClient(...)
    return _chroma_client
```

这是一个标准的**双重检查锁定（DCL）单例模式**。

### 3.2 问题分析

#### 问题 3.2.1 [P0] 同步阻塞调用直接跑在事件循环中

这是本次评审发现的**最严重问题**。

**`upload_document` 路径**（`knowledge_service.py:25` + `api/knowledge.py:29`）：

```python
# api/knowledge.py — async 路由
@router.post("/documents/upload")
async def upload_document(...):
    content = await file.read()        # ← 这是异步的
    doc = await service.upload_document(...)  # ← 下面全是同步阻塞！

# knowledge_service.py — async 方法但内部全同步
async def upload_document(self, ...):
    file_path.write_bytes(content)      # 同步文件 I/O，阻塞事件循环
    text = parse_file(...)              # 同步 CPU 密集（PDF 解析），阻塞
    chunks = chunk_text(...)            # 同步 CPU 密集，阻塞
    embeddings = self.embedding_service.embed_texts(texts)  # 同步 HTTP 调用，阻塞！
    collection.add(...)                 # 同步 SQLite 写入，阻塞
```

整个上传流水线（文件写入 → PDF 解析 → 分块 → Embedding API 调用 → ChromaDB 写入）都是同步阻塞操作，却在 `async def` 中直接调用。这意味着**一个文档上传会阻塞整个事件循环**，期间所有其他请求（包括健康检查、其他租户的对话）都会被挂起。

对于 Demo 演示，如果上传一个较大的 PDF（比如 5MB），解析 + embedding 可能耗时数秒到数十秒，期间整个服务完全无响应。

**`/retrieve` 路径**（`api/knowledge.py:77`）：

```python
@router.post("/retrieve")
async def retrieve(request, ...):
    results = service.retrieve(...)  # 同步方法，collection.query() 阻塞事件循环
```

同理，检索也是同步阻塞。

**`kb_retrieval` 工具**（`agent/tools.py:44`）：

```python
@tool("kb_retrieval")
def kb_retrieval(query: str) -> str:  # 同步函数
    results = service.retrieve(...)   # 同步调用
```

这个反而问题较小——LangGraph 会将同步 `@tool` 函数放到线程池中执行，不会阻塞事件循环。但 `/retrieve` API 和 `upload_document` 路由是 `async def`，不会被自动放到线程池。

#### 问题 3.2.2 [P1] _chroma_lock 仅保护单例创建，不保护 CRUD 操作

`_chroma_lock` 只在 `get_chroma_client()` 的 DCL 中使用，创建完客户端后就不再加锁。所有 `collection.add()` / `collection.query()` / `collection.delete()` 调用都不受锁保护。

ChromaDB PersistentClient 底层使用 SQLite。SQLite 默认有文件级锁，但在高并发写入时可能出现 `database is locked` 错误。对于 Demo 单用户场景这不太会触发，但如果多个请求同时上传文档（比如前端批量上传），可能遇到写锁冲突。

#### 问题 3.2.3 [P2] collection 对象未缓存，每次操作都重新获取

`get_or_create_collection()` 在每次 upload / retrieve / delete 时都被调用。虽然 `get_or_create` 语义上是幂等的，但每次调用都要查询 collection 是否存在，有不必要的开销。建议缓存 collection 对象（按 tenant_id）。

### 3.3 修复建议

| 问题 | 修复方案 |
|------|---------|
| P0 阻塞事件循环 | 将 `upload_document` 中的同步阻塞操作用 `asyncio.to_thread()` 或 `loop.run_in_executor()` 包装；或将路由改为 `def`（非 async），FastAPI 会自动放入线程池 |
| P1 CRUD 无锁 | Demo 级可接受，但建议对 `collection.add()` 加操作级锁或使用 `asyncio.to_thread` 避免并发写冲突 |
| P2 collection 未缓存 | 增加 `{tenant_id: Collection}` 字典缓存，避免重复 `get_or_create` |

---

## 4. 数据一致性评审

### 4.1 当前双写架构

```
upload_document:
  ① DocumentStore.add_document(doc)         ← 内存 dict，先写
  ② DocumentStore.add_chunks(doc_id, chunks) ← 内存 dict
  ③ collection.add(ids, embeddings, ...)     ← ChromaDB，后写
  ④ DocumentStore.update_document(status=READY)

delete_document:
  ① DocumentStore.get_chunks(doc_id)         ← 从内存获取 chunk_id 列表
  ② collection.delete(ids=[chunk_ids])       ← ChromaDB 先删
  ③ Path(doc.file_path).unlink()             ← 删文件
  ④ DocumentStore.delete_document(doc_id)    ← 内存后删
```

### 4.2 问题分析

#### 问题 4.2.1 [P0] upload 异常路径数据不一致

```python
# knowledge_service.py:80-107
if chunks:
    texts = [c.content for c in chunks]
    embeddings = self.embedding_service.embed_texts(texts)  # ← 可能抛异常
    collection = get_or_create_collection(tenant_id)
    collection.add(...)                                      # ← 可能抛异常

# 如果上面抛异常，下面这行不会执行
self.store.update_document(doc_id, status=DocumentStatus.READY, ...)
```

如果 `embed_texts()` 或 `collection.add()` 抛异常：
- DocumentStore 中文档状态卡在 `EMBEDDING`，永远不会变成 `READY` 或 `FAILED`
- DocumentStore 中已有 document 记录和 chunks 记录，但 ChromaDB 中没有向量数据
- 用户看到文档状态永远是"向量化中"，但实际上已经失败了

**没有 try/except 包裹 embedding + ChromaDB 写入，也没有状态回滚或标记失败。**

#### 问题 4.2.2 [P1] delete 异常静默吞错

```python
# knowledge_service.py:130-135
try:
    collection.delete(ids=[c.chunk_id for c in chunks])
except Exception:
    pass  # ← 静默吞掉所有异常
```

如果 ChromaDB 删除失败（比如写锁冲突），异常被吞掉，但后续仍然会删除文件和 DocumentStore 记录。结果是：ChromaDB 中残留孤儿向量，但 DocumentStore 中已无 chunk_id 信息，这些孤儿向量永远无法被清理。

#### 问题 4.2.3 [P1] 无事务/补偿机制

两个存储（内存 DocumentStore + ChromaDB）之间没有任何事务保证：
- 没有先写日志再执行的两阶段提交
- 没有失败后的补偿/回滚逻辑
- 没有定时对账机制（检查 DocumentStore 与 ChromaDB 数据是否一致）

对于 Demo 项目，不需要引入完整的事务机制，但至少应该：
1. upload 失败时将文档状态标记为 `FAILED` 并记录错误信息
2. delete ChromaDB 失败时不要继续删除 DocumentStore（或至少记录警告日志）

#### 问题 4.2.4 [P2] 内存存储重启即失，但 ChromaDB 持久化

`DocumentStore` 是纯内存 dict，服务重启后所有文档元数据丢失。但 ChromaDB 是持久化的（`PersistentClient` 写磁盘）。重启后：
- ChromaDB 中有向量数据，但 DocumentStore 不知道这些文档的存在
- `list_documents()` 返回空列表，但 `retrieve()` 仍然能检索到向量
- 用户无法管理（删除）这些"幽灵文档"的向量数据

这在 Demo 演示中会造成困惑——重启后知识库"还在"但文档管理页"空了"。

---

## 5. 距离转相似度公式评审

### 5.1 当前公式

```python
# retrieval_service.py:92
score = max(0.0, 1.0 - distance / 2.0)
```

### 5.2 正确性分析

这个公式的正确性取决于三个隐式假设：

| 假设 | 当前是否满足 | 说明 |
|------|-------------|------|
| ChromaDB 使用 L2 空间（默认） | ✅ 是 | `get_or_create_collection` 未指定 `hnsw:space`，ChromaDB 默认使用 L2 |
| ChromaDB L2 返回平方欧氏距离 ‖a-b‖² | ✅ 是 | HNSWlib 的 L2 空间返回平方距离 |
| Embedding 向量已归一化（单位向量） | ✅ 是 | OpenAI text-embedding-v3 返回归一化向量；本地回退 `_local_embed` 也做了归一化 |

在以上三个假设同时满足时，公式推导：

```
L2 平方距离 = ‖a - b‖² = ‖a‖² + ‖b‖² - 2(a·b) = 2 - 2cos(θ)  （单位向量）
score = 1 - distance/2 = 1 - (2 - 2cos(θ))/2 = cos(θ)  ✅ 正确
```

**结论：当前公式在现有条件下是数学正确的。**

### 5.3 风险分析

#### 风险 5.3.1 [P1] 距离度量未显式声明，依赖默认值

`get_or_create_collection` 没有显式设置 `metadata={"hnsw:space": "l2"}`。如果未来 ChromaDB 版本修改默认距离度量（虽然不太可能），或者有人在创建 collection 时传入了不同的 `hnsw:space`，公式会静默出错。

不同距离度量下的公式表现：

| hnsw:space | distance 含义 | distance 范围 | `1 - d/2` 的结果 | 是否等于 cosine |
|-----------|--------------|--------------|-----------------|----------------|
| l2（默认） | ‖a-b‖² 平方欧氏 | [0, 4] | [1, -1] → 即 cos(θ) | ✅ 是 |
| cosine | 1 - cos(θ) | [0, 2] | [1, 0] → 即 (1+cos)/2 | ❌ 否（偏差） |
| ip | -内积 | (-∞, +∞) | 不确定 | ❌ 否 |

#### 风险 5.3.2 [P2] 归一化假设脆弱

如果未来切换到不返回归一化向量的 embedding 模型，公式会出错。当前代码中 embedding 维度是硬编码的（`embedding_service.py:22-27`），但归一化是隐式依赖 embedding API 的行为。

### 5.4 修复建议

```python
# 建议方案：显式声明距离度量 + 更健壮的转换
def get_or_create_collection(tenant_id: str):
    client = get_chroma_client()
    collection_name = f"tenant-{tenant_id}-kb"
    return client.get_or_create_collection(
        name=collection_name,
        metadata={
            "tenant_id": tenant_id,
            "hnsw:space": "cosine",  # 显式使用 cosine，语义最清晰
        },
    )

# 转换公式也相应调整（cosine space 下）：
# distance = 1 - cos(θ)，所以 similarity = 1 - distance
score = max(0.0, 1.0 - distance)
```

或者保持 L2 但显式声明：
```python
metadata={"hnsw:space": "l2"}  # 显式声明，不依赖默认值
# 公式不变：score = max(0.0, 1.0 - distance / 2.0)
```

---

## 6. 其他发现

### 6.1 [P1] collection.count() 重复调用 + TOCTOU 竞态

```python
# retrieval_service.py:69
n_results=min(top_k, collection.count()) if collection.count() > 0 else top_k
```

`collection.count()` 被调用了两次（两次 SQLite 查询），且两次调用之间数据可能变化（Time-Of-Check-Time-Of-Use 竞态）。应改为：

```python
count = collection.count()
n_results = min(top_k, count) if count > 0 else top_k
```

### 6.2 [P1] Embedding 服务异常静默回退到随机向量

```python
# embedding_service.py:60-70
try:
    response = client.embeddings.create(...)
    return [item.embedding for item in response.data]
except Exception:
    pass  # ← 静默回退到本地伪随机向量

return [self._local_embed(text) for text in texts]  # 随机向量！
```

如果 Embedding API 调用失败（网络错误、API Key 过期、配额耗尽），代码静默回退到**基于哈希的伪随机向量**。这意味着：
- 文档会被"成功"上传，状态变成 `READY`
- 但向量是随机的，检索结果完全无意义
- 用户毫无感知，以为系统正常工作

对于 Demo 这是致命的——演示时如果 API Key 过期，检索返回的是随机结果，会非常尴尬。至少应该记录警告日志，或者在 API Key 配置时做一次连通性检查。

### 6.3 [P2] upload_document 中重复 import

```python
# knowledge_service.py:47
from app.config import settings  # 函数内 import
```

`settings` 在模块顶部已经可以通过 `from app.config import settings` 引入，函数内 import 是不必要的延迟导入。虽然不影响功能，但不够规范。

### 6.4 [P2] delete_collection 吞掉所有异常

```python
# database.py:56-59
try:
    client.delete_collection(name=collection_name)
except Exception:
    pass  # 集合不存在时忽略
```

注释说"集合不存在时忽略"，但 `except Exception` 会吞掉所有异常（包括权限错误、磁盘满、SQLite 锁等），不仅仅是"集合不存在"。应该精确捕获 `chromadb.errors.CollectionNotFoundError`（或检查返回值）。

---

## 7. 问题汇总与优先级

| 编号 | 优先级 | 问题 | 所在文件 | 影响 |
|------|--------|------|---------|------|
| 3.2.1 | **P0** | 同步阻塞调用直接跑在事件循环中 | `knowledge_service.py`, `api/knowledge.py` | 上传/检索阻塞整个服务，高并发下服务无响应 |
| 4.2.1 | **P0** | upload 异常路径无 try/except，状态卡死 | `knowledge_service.py:80-100` | embedding 失败后文档状态永远卡在 EMBEDDING |
| 6.2 | **P0** | Embedding 失败静默回退随机向量 | `embedding_service.py:60-70` | API 异常时检索返回随机结果，用户无感知 |
| 2.2.1 | **P1** | tenant_id 未校验，collection 名称注入风险 | `database.py:41` | 恶意/异常 tenant_id 导致 collection 冲突 |
| 2.2.2 | **P1** | 查询缺少 where 条件二次过滤 | `retrieval_service.py:67` | 无纵深防御，collection 碰撞时跨租户泄露 |
| 3.2.2 | **P1** | CRUD 操作无锁保护 | `database.py` | 并发写可能触发 SQLite 锁错误 |
| 4.2.2 | **P1** | delete 异常静默吞错，产生孤儿向量 | `knowledge_service.py:130-135` | ChromaDB 残留无法清理的向量 |
| 4.2.3 | **P1** | 无事务/补偿机制 | `knowledge_service.py` | 双写不一致无恢复手段 |
| 5.3.1 | **P1** | 距离度量未显式声明 | `database.py:42-45` | 公式依赖隐式默认值，脆弱 |
| 6.1 | **P1** | collection.count() 重复调用 + 竞态 | `retrieval_service.py:69` | 性能浪费 + TOCTOU 竞态 |
| 2.2.3 | **P2** | list_collections() 不区分租户 | `database.py:62-65` | 全局 collection 名称泄露 |
| 2.2.4 | **P2** | 文档与代码不一致 | `docs/architecture.md` | 文档说 `tenant-{id}-kb-{name}`，代码是 `tenant-{id}-kb` |
| 3.2.3 | **P2** | collection 对象未缓存 | `database.py` | 每次操作重复 get_or_create |
| 4.2.4 | **P2** | 内存存储重启即失，ChromaDB 持久化 | `document.py` DocumentStore | 重启后向量数据变"幽灵" |
| 5.3.2 | **P2** | 归一化假设脆弱 | `embedding_service.py` | 换 embedding 模型可能破坏公式 |
| 6.3 | **P2** | 函数内重复 import | `knowledge_service.py:47` | 代码规范 |
| 6.4 | **P2** | delete_collection 吞掉所有异常 | `database.py:56-59` | 掩盖非"不存在"类错误 |

---

## 8. 改进建议优先级路线图

### P0（必须修复，影响 Demo 可用性）

1. **解除事件循环阻塞**：将 `upload_document` 内部的同步操作用 `asyncio.to_thread()` 包装，或将路由函数从 `async def` 改为 `def`（FastAPI 自动线程池）。同理修改 `/retrieve` 路由。

2. **upload 异常处理**：在 embedding + ChromaDB 写入外层加 try/except，失败时将文档状态标记为 `FAILED` 并记录 `error_message`。

3. **Embedding 回退告警**：当回退到本地伪随机向量时，至少记录 `logger.warning`；建议在启动时做一次 embedding API 连通性检查，失败则明确告警。

### P1（建议修复，提升健壮性）

4. **tenant_id 校验**：在 `get_or_create_collection` 中校验 tenant_id 格式（正则 `^[a-zA-Z0-9_-]+$`，长度限制）。
5. **查询 where 过滤**：在 `collection.query()` 中增加 `where={"tenant_id": tenant_id}`。
6. **显式声明距离度量**：在 collection metadata 中增加 `"hnsw:space": "cosine"`，并调整转换公式为 `score = 1 - distance`。
7. **delete 异常处理**：精确捕获异常，失败时记录日志并中止删除流程（或至少不继续删 DocumentStore）。
8. **count() 单次调用**：修复 `retrieval_service.py:69` 的重复调用。

### P2（长期优化）

9. collection 对象缓存
10. 文档与代码对齐
11. 内存存储 → SQLite 持久化（架构文档 P1 计划已有）
12. list_collections 增加租户过滤

---

*评审完毕。以上问题均已定位到具体代码行，可直接据此修改。*
