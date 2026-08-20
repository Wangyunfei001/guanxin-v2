# DeepSeek Agent 与 Ollama Embedding 接入设计

## 1. 目标与边界

本轮将 Agent 固定接入 DeepSeek 官方 OpenAI 兼容接口，并将知识库向量生成切换为本机 Ollama 中已安装的 `bge-m3:latest`。Embedding 不再请求远程供应商，也不在 Ollama 故障时静默退化为随机向量。

本轮不更换聊天协议、不调整 Agent 提示词或工具权限，也不引入新的模型运行框架。DeepSeek API Key 只写入被 Git 忽略的 `backend/.env`，不会进入源码、测试、日志或文档。

## 2. 方案选择

采用显式 Ollama provider，而不是把 Ollama 伪装成需要假 API Key 的 OpenAI Embedding 服务。

- Agent：`OPENAI_API_BASE=https://api.deepseek.com`，模型使用 `deepseek-v4-flash`。
- Embedding：`EMBEDDING_PROVIDER=ollama`，`OLLAMA_BASE_URL=http://127.0.0.1:11434`，模型使用 `bge-m3:latest`。
- Ollama 调用原生 `POST /api/embed`，批量传入文本并读取 `embeddings`。
- 已安装的 `bge-m3:latest` 输出 1024 维向量；服务必须验证返回数量、维度一致性和数值结构。

不采用仅修改远程 Embedding URL 的兼容方案，因为现有实现会从 `OPENAI_API_KEY` 回填 Embedding Key，Ollama 离线时还会生成 1536 维随机向量，与 `bge-m3` 的 1024 维索引不兼容。

## 3. 配置与组件设计

### 3.1 Settings

新增以下配置：

- `EMBEDDING_PROVIDER`：`openai`、`ollama` 或 `local`，本机演示环境使用 `ollama`。
- `OLLAMA_BASE_URL`：默认 `http://127.0.0.1:11434`。
- `EMBEDDING_DIMENSION`：本机配置为 `1024`，用于验证模型输出。

保留现有 `EMBEDDING_API_BASE` 和 `EMBEDDING_API_KEY`，仅供 `openai` provider 使用。`ollama` provider 不读取任何远程 Embedding Key。

### 3.2 EmbeddingService

`EmbeddingService` 保持现有公共方法不变：`embed_texts`、`embed_texts_with_fallback`、`embed_query` 和 `check_connectivity`，以避免知识库与检索服务改造。

- `openai`：保留现有 OpenAI 兼容调用及旧的确定性本地回退行为。
- `local`：直接使用确定性本地向量，作为显式兼容模式。
- `ollama`：使用同步 HTTP 客户端调用原生 Ollama API；成功时返回语义向量且 `is_fallback=False`。
- Ollama 超时、响应格式错误、向量数量或维度不符时抛出明确异常，不生成随机向量。
- `check_connectivity` 对 Ollama 执行一次本地探针并验证 1024 维结果，不访问公网。

这样上传失败会沿用现有补偿逻辑，将文档标记为 `FAILED`；查询失败会向上返回明确错误，避免把坏向量写入 Chroma。

## 4. 数据迁移

现有 Chroma 数据由 1536 维远程或回退向量生成，不能与 1024 维 `bge-m3` 混用。实施时执行一次精确重建：

1. 保留 `backend/data/users.json`、对话、Agent 配置和审批数据。
2. 删除当前示例文档记录、document chunks、对应上传文件和 Chroma 索引。
3. 启动应用，通过现有幂等种子重新创建每租户两份示例文档。
4. 确认四份文档全部为 `READY`，Chroma 向量维度为 1024。

本轮数据均为此前重建的演示种子，因此不增加通用在线向量迁移器。

## 5. 验证与错误处理

自动测试不得访问 DeepSeek 或真实 Ollama：

- mock Ollama 批量响应，验证请求契约、顺序和 1024 维输出。
- 验证 Ollama 模式不读取 `OPENAI_API_KEY` 或 `EMBEDDING_API_KEY`。
- 验证 Ollama 不可用、返回数量错误和维度错误时明确失败且不随机回退。
- 保留并更新现有 OpenAI/local provider 回归测试。
- 后端全量测试、前端 lint/typecheck/build 必须继续通过。

本机验收使用真实 `bge-m3:latest`：

- Ollama 探针成功并返回 1024 维向量。
- 四份示例文档完成重建，知识库查询能够返回当前租户的相关来源。
- DeepSeek 只做不产生文本生成费用的认证/模型可用性检查；除非用户另行要求，不发送第二次付费聊天 smoke。

## 6. 文档与安全

- `.env.example` 与 README 增加 Ollama 启动、拉取模型和配置说明，但只使用占位 Key。
- 日志只记录 provider、模型、连通性和错误类型，不记录请求头或 API Key。
- `backend/.env` 继续由 `.gitignore` 排除。

## 7. 完成条件

- Agent 配置使用 DeepSeek 官方端点和 `deepseek-v4-flash`。
- Embedding 请求只发往本机 Ollama，远程 Embedding Key 为空。
- Ollama 故障不会写入随机或维度不一致的向量。
- 示例知识库全部以 `bge-m3:latest` 重建并可检索。
- 自动测试、静态检查、生产构建和本机连通性验证全部通过。
