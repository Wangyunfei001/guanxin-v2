# v0.2.0-demo 操作手册

## 演示前

1. 使用 Python 3.13、Node 20+，安装后端 `.[dev]` 与前端 `npm ci`。
2. 从 `backend/.env.example` 配置真实 DeepSeek API Key；启动 Ollama 并确认 `ollama list` 包含 `bge-m3:latest`。
3. 使用独立临时根目录设置 `DATABASE_PATH`、`CHECKPOINT_DATABASE_PATH`、`CHROMA_PERSIST_DIR`、`UPLOAD_DIR`、`USER_DATA_PATH`，不要清理日常开发数据。
4. 启动后端和前端，确认 `/health` 返回 `version: 0.2.0`。默认地址为 localhost:8000/3000。
5. 如默认端口已被使用，可另起后端 18001，前端设置 `GUANXIN_BACKEND_URL=http://127.0.0.1:18001 NEXT_DIST_DIR=.next-acceptance`，运行 `npm run dev -- --port 13001`。

## 七组演示

| 场景 | 操作 | 成功判据 |
|---|---|---|
| PDF 与引用 | admin 登录，上传带独有验收码的文本 PDF；查看切片；检索验收码；在 Assistant 要求基于知识库回答并注明文件名 | 就绪、切片非空、检索命中、回答含正确码和来源 |
| Skill 与 A2UI | 新会话输入“请调用 Data Analysis Skill 对 [12,18,21,27,42] 做完整分析” | 工具轨迹、mean=24、数据可视化柱状图同时出现；A2UI 实验室可查看 Schema |
| 天气 MCP | MCP 页面连接 weather；新会话输入“查询北京当前真实天气并注明来源” | mcp__weather__get_weather 被调用，结果 source=Open-Meteo、simulated=false |
| 对外 MCP | 按 README 获取当前 API Key；运行 `backend/.venv/bin/python scripts/verify-mcp-server.py` | initialize、发现且仅发现三个工具，三个调用无 isError |
| Quick/Deep Research | 分别选择快速研究、深度研究；输入聚焦的公开问题，如“MCP 官方定义是什么？请引用官方来源并说明证据边界” | 状态 completed、无 error、报告非空且有来源；超时部分报告不算通过 |
| 写工作流恢复 | 在 Agent 配置启用 create_user；新会话要求“创建一个用户”；补用户名和邮箱；等待审批后刷新页面，再重启后端并刷新，最后批准执行 | 同一流程恢复，无重复创建；最终完成，查询用户仅一条；刷新后最终结果仍在 |
| 租户隔离 | tenant-a 上传唯一文档并创建会话；退出后 demo 登录 tenant-b；再反向验证 | 文档列表、详情、检索、会话互不可见；user 无权修改 Agent 配置 |

真实 Research 依赖 DeepSeek Responses/Web Search，建议预留数分钟。默认 Quick 90 秒、Deep 480 秒；Next.js 代理允许最长 10 分钟。provider 单次调用硬截止 60 秒，失败后检查连接再新建会话重试，不用失败/部分结果代替完整验收。

## 演示后

- 删除本轮创建的演示文档、业务用户和会话，或停止独立验收服务后回收已确认的临时根目录。
- 不删除 `backend/data` 或用户正在使用的数据目录。
- 后端重启会生成新的预设 API Key；刷新外部 MCP 客户端配置。Key 和模型凭证均不应进入截图、报告或 Git。
- 数据库、checkpoint 与向量目录应成组保留；只移动其中一部分会破坏恢复和检索的一致性。
