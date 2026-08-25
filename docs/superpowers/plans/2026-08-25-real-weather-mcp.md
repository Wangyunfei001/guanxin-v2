# 真实天气 MCP 实施计划

## 目标

在不改变 `mcp__weather__get_weather` 工具名和 Agent 调用协议的前提下，将内置天气 MCP Server 替换为 Open-Meteo 真实当前天气查询。

## 实施步骤

1. 在 `backend/app/mcp/weather_server.py` 中增加城市解析、天气查询、WMO 中文描述映射和结果规范化。
2. 使用项目已有 `httpx` 异步客户端，设置请求超时，并用专用异常向 MCP 返回安全错误。
3. 保持现有 `city`、`unit` 输入兼容；成功结果返回 `simulated=false`、来源、位置、观测时间和真实气象字段。
4. 将工具 annotation 的 `openWorldHint` 调整为 `true`，更新 Server、种子数据和 README 中的模拟描述。
5. 新增完全 mock 上游 HTTP 的单元测试，覆盖成功、单位、天气代码、无城市、超时、HTTP 错误和畸形响应。
6. 运行天气测试及后端全量测试；随后只执行一次 Open-Meteo 联网 smoke test。
7. 检查差异和敏感信息，以中文提交本轮实现，不提交用户现有 `.gitignore` 修改。

## 验收条件

- 查询北京返回 `simulated=false` 和 `source=Open-Meteo`。
- 输出含规范城市、经纬度、时区、观测时间、温度、体感温度、湿度、天气描述与风速。
- 上游失败时不生成随机数据，不泄露内部错误。
- 原工具名、输入 schema、只读策略、Supervisor 路由和历史持久化兼容。
- 后端测试全绿，真实联网 smoke test 成功。
