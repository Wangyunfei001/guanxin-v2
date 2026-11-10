---
id: knowledge
type: module-design
title: 知识库与向量检索
status: draft
parent: architecture
depends-on: [platform-core]
references: [doc-chroma-review]
---

# 知识库与向量检索

## 职责

租户内文档从上传到可检索的全流程：解析、分块、生成向量、写入 ChromaDB、按语义检索，并把每一步的成败如实落在文档状态上。

## 边界

- 只经 `core/database.py` 访问 ChromaDB，经 `platform-core` 的 SQLite 访问文档元数据；不直接持有客户端单例。
- 租户隔离靠 collection 粒度（每租户 `tenant-{tenant_id}-kb`），检索结果只回给出当前租户。
- 不做 OCR，不做语义重排，也不替模型判断答案是否成立。

## 契约

**状态机**：`pending → parsing → chunking → embedding → ready | failed`，失败时写 `error_message`；任何阶段异常都落到 `failed`，不会停在中间状态。

**写入顺序与补偿**：先建业务记录 → 存文件 → 解析 → 分块入库 → 写向量 → 标记 ready。向量写入失败时按 chunk id 补偿已写入部分，再把文档标为 failed。

**删除顺序**：先校验租户归属，Chroma 删除失败即中止（避免残留孤儿向量的同时丢元数据），成功后才删文件与 SQLite 记录。

**不阻塞事件循环**：整条同步流水线（文件写入、解析、分块、Embedding、Chroma 写入）在线程池执行；检索同样走线程池。

**分块**：默认 500 字符、50 字符重叠、按空行分段；块元数据带 `doc_id`、`tenant_id`、`filename`、`chunk_index` 与 `fallback` 标记。

**向量来源**：显式 provider 配置。`ollama` 用本机 `bge-m3`（1024 维）；`openai` 走兼容接口，失败时记录告警并把该批块标为 `fallback`；`local` 明确使用确定性伪随机向量。Ollama 不可用时知识库不会静默写入随机向量。

**支持格式**：txt / md / pdf（文本层）/ docx / json / csv 与常见代码文本；未知后缀按文本读取。

## 已知限制

- 距离度量依赖 ChromaDB 默认 L2，相似度按 `max(0, 1 - distance/2)` 换算；换 provider 或换 `hnsw:space` 需同步改公式。
- 检索没有额外的租户 `where` 二次过滤，隔离完全依赖 collection 命名。
- 单进程内共享 Chroma PersistentClient；运维细节与未闭环风险见 `doc-chroma-review`。
