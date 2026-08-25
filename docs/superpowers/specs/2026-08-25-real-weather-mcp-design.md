# 真实天气 MCP 设计规格

## 目标

将内置 `weather` MCP Server 从随机模拟数据切换为 Open-Meteo 真实天气数据，同时保持 `mcp__weather__get_weather` 工具名、输入契约和 Agent 调用链路稳定。

本次只替换天气 MCP Server 内部的数据来源，不改变 Supervisor、Tool Catalog、对话协议或前端工具渲染协议。

## 数据源与边界

- 地理编码使用 Open-Meteo Geocoding API，将用户输入的城市名解析为经纬度、规范城市名、行政区和时区。
- 当前天气使用 Open-Meteo Forecast API，读取温度、体感温度、相对湿度、WMO 天气代码和 10 米风速。
- Server 使用地理编码结果中的时区请求当地时间，不根据服务器所在时区推断。
- 不增加 API Key 配置，不引入新的天气供应商抽象层。
- 不提供未来预报、空气质量、天气预警或历史天气；这些能力以后通过新增工具独立扩展。

官方接口：

- <https://open-meteo.com/en/docs/geocoding-api>
- <https://open-meteo.com/en/docs>

## 工具契约

工具继续使用：

```text
mcp__weather__get_weather
```

输入保持兼容：

```json
{
  "city": "北京",
  "unit": "celsius"
}
```

`city` 必填并去除首尾空白；空字符串拒绝执行。`unit` 仅允许 `celsius` 或 `fahrenheit`，默认 `celsius`。

成功输出统一为结构化 JSON：

```json
{
  "simulated": false,
  "source": "Open-Meteo",
  "source_url": "https://open-meteo.com/",
  "city": "北京",
  "admin1": "北京市",
  "country": "中国",
  "latitude": 39.9075,
  "longitude": 116.39723,
  "timezone": "Asia/Shanghai",
  "observed_at": "2026-08-25T13:45",
  "temperature": "27.7°C",
  "apparent_temperature": "33.5°C",
  "condition": "雷阵雨",
  "weather_code": 96,
  "humidity": "82%",
  "wind_speed": "3.4 km/h",
  "unit": "celsius"
}
```

WMO 天气代码在 Server 内映射为稳定的中文描述。华氏温度通过 Open-Meteo 的 `temperature_unit=fahrenheit` 获取，避免服务端重复换算和单位舍入差异。

## 数据流

1. Agent 选择 `mcp__weather__get_weather` 并传入城市。
2. MCP Server 校验参数。
3. Server 请求 Geocoding API，选择首个有效城市结果。
4. Server 使用经纬度和时区请求 Forecast API 的 `current` 数据。
5. Server 校验必要字段、转换天气代码并返回结构化结果。
6. 现有 MCP Client 将结果作为 Tool Message 返回模型，并由现有持久化链路保存调用 ID、输入和输出。

## 错误处理

- HTTP 客户端设置明确连接与总请求超时，不无限等待外部服务。
- 城市无匹配结果时返回可理解的工具错误，提示用户补充省份或国家，不回退到随机数据。
- Open-Meteo 超时、非成功状态、响应格式异常或缺少必要字段时返回“天气服务暂时不可用”的结构化错误。
- 错误内容不包含调用栈、内部路径或敏感配置。
- MCP Server 保持运行；单次上游失败不能导致 stdio Server 退出。
- `openWorldHint` 调整为 `true`，准确表达该只读工具会访问外部网络；`readOnlyHint=true` 保持不变。

## 实现结构

- 在 `backend/app/mcp/weather_server.py` 内保留 MCP 注册层，并将数据访问拆为小型异步函数：城市解析、天气请求、结果规范化。
- 复用项目已有异步 HTTP 依赖；若现有依赖不能满足要求，再添加最小依赖，不引入天气 SDK。
- MCP 工具描述、Server 描述、README 和种子说明统一改为“真实天气”。
- 保留现有工具名与 Server 名，已连接租户无需重新配置。

## 测试与验收

自动测试全部 mock Open-Meteo，不依赖公网：

- 北京查询会向地理编码接口传递中文城市名。
- 经纬度、时区和当前天气字段正确传递与规范化。
- 摄氏和华氏单位正确。
- 常见 WMO 天气代码得到中文描述，未知代码有安全兜底。
- 城市不存在、超时、HTTP 错误、畸形 JSON 和字段缺失均返回明确错误，且绝不产生模拟数据。
- MCP schema、只读策略和现有 Agent 工具名保持兼容。

完成自动测试后只执行一次人工联网 smoke test：连接天气 MCP，询问“北京市今天天气怎么样”，确认工具输出包含 `simulated=false`、Open-Meteo 来源和观测时间，并确认回答正文不再声称是模拟数据。

## 非目标

- 不缓存天气结果。
- 不保存第三方原始响应。
- 不接入需要 API Key 的商业天气供应商。
- 不将天气能力改造成 Skill 或 Provider Tool。
- 不修改 Deep Research 的 Web Search 实现。
