"""基于 Open-Meteo 的真实天气查询 MCP Server。"""

import asyncio
from typing import Any, Dict, Mapping, Optional

import httpx


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT = httpx.Timeout(10.0, connect=5.0)

CURRENT_FIELDS = (
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "weather_code",
    "wind_speed_10m",
)

WMO_CONDITIONS = {
    0: "晴",
    1: "大部晴朗",
    2: "局部多云",
    3: "阴",
    45: "雾",
    48: "雾凇",
    51: "小毛毛雨",
    53: "毛毛雨",
    55: "强毛毛雨",
    56: "轻微冻毛毛雨",
    57: "强冻毛毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    66: "轻微冻雨",
    67: "强冻雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    77: "米雪",
    80: "小阵雨",
    81: "中阵雨",
    82: "强阵雨",
    85: "小阵雪",
    86: "强阵雪",
    95: "雷暴",
    96: "雷暴伴小冰雹",
    99: "雷暴伴大冰雹",
}


class WeatherServiceError(RuntimeError):
    """可安全返回给 MCP 调用方的天气服务错误。"""


def describe_weather_code(code: int) -> str:
    """将 WMO 天气代码转换为稳定的中文描述。"""
    return WMO_CONDITIONS.get(code, f"未知天气（WMO {code}）")


def _required(mapping: Mapping[str, Any], key: str) -> Any:
    value = mapping.get(key)
    if value is None:
        raise WeatherServiceError("天气服务返回的数据不完整，请稍后重试")
    return value


async def _request_json(
    client: httpx.AsyncClient,
    url: str,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        response = await client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
    except httpx.TimeoutException as exc:
        raise WeatherServiceError("天气服务请求超时，请稍后重试") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise WeatherServiceError("天气服务暂时不可用，请稍后重试") from exc

    if not isinstance(payload, dict):
        raise WeatherServiceError("天气服务返回的数据格式异常，请稍后重试")
    return payload


async def resolve_city(client: httpx.AsyncClient, city: str) -> Dict[str, Any]:
    """将城市名解析为 Open-Meteo 位置数据。"""
    payload = await _request_json(
        client,
        GEOCODING_URL,
        {
            "name": city,
            "count": 1,
            "language": "zh",
            "format": "json",
        },
    )
    results = payload.get("results")
    if not isinstance(results, list) or not results:
        raise WeatherServiceError(
            f"未找到城市“{city}”，请补充省份或国家后重试"
        )

    location = results[0]
    if not isinstance(location, dict):
        raise WeatherServiceError("天气服务返回的位置数据异常，请稍后重试")
    _required(location, "name")
    _required(location, "latitude")
    _required(location, "longitude")
    _required(location, "timezone")
    return location


async def fetch_current_weather(
    client: httpx.AsyncClient,
    location: Mapping[str, Any],
    unit: str,
) -> Dict[str, Any]:
    """获取指定位置的真实当前天气并规范化结果。"""
    temperature_unit = "fahrenheit" if unit == "fahrenheit" else "celsius"
    payload = await _request_json(
        client,
        FORECAST_URL,
        {
            "latitude": _required(location, "latitude"),
            "longitude": _required(location, "longitude"),
            "current": ",".join(CURRENT_FIELDS),
            "timezone": _required(location, "timezone"),
            "temperature_unit": temperature_unit,
            "wind_speed_unit": "kmh",
        },
    )

    current = payload.get("current")
    current_units = payload.get("current_units")
    if not isinstance(current, dict) or not isinstance(current_units, dict):
        raise WeatherServiceError("天气服务返回的数据不完整，请稍后重试")

    weather_code = _required(current, "weather_code")
    if not isinstance(weather_code, (int, float)):
        raise WeatherServiceError("天气服务返回的天气代码异常，请稍后重试")
    normalized_code = int(weather_code)

    temperature = _required(current, "temperature_2m")
    apparent_temperature = _required(current, "apparent_temperature")
    humidity = _required(current, "relative_humidity_2m")
    wind_speed = _required(current, "wind_speed_10m")

    temperature_symbol = current_units.get(
        "temperature_2m", "°F" if unit == "fahrenheit" else "°C"
    )
    apparent_symbol = current_units.get(
        "apparent_temperature", temperature_symbol
    )
    humidity_symbol = current_units.get("relative_humidity_2m", "%")
    wind_symbol = current_units.get("wind_speed_10m", "km/h")

    return {
        "simulated": False,
        "source": "Open-Meteo",
        "source_url": "https://open-meteo.com/",
        "city": _required(location, "name"),
        "admin1": location.get("admin1"),
        "country": location.get("country"),
        "latitude": _required(location, "latitude"),
        "longitude": _required(location, "longitude"),
        "timezone": payload.get("timezone") or _required(location, "timezone"),
        "observed_at": _required(current, "time"),
        "temperature": f"{temperature}{temperature_symbol}",
        "apparent_temperature": f"{apparent_temperature}{apparent_symbol}",
        "condition": describe_weather_code(normalized_code),
        "weather_code": normalized_code,
        "humidity": f"{humidity}{humidity_symbol}",
        "wind_speed": f"{wind_speed} {wind_symbol}",
        "unit": unit,
    }


async def handle_get_weather(
    city: str,
    unit: str = "celsius",
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """查询城市的真实当前天气。"""
    normalized_city = city.strip() if isinstance(city, str) else ""
    if not normalized_city:
        raise WeatherServiceError("城市名称不能为空")
    if unit not in {"celsius", "fahrenheit"}:
        raise WeatherServiceError("温度单位仅支持 celsius 或 fahrenheit")

    if client is not None:
        location = await resolve_city(client, normalized_city)
        return await fetch_current_weather(client, location, unit)

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as owned_client:
        location = await resolve_city(owned_client, normalized_city)
        return await fetch_current_weather(owned_client, location, unit)


async def main() -> None:
    """MCP Server 主入口。"""
    try:
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        from mcp.types import Tool, ToolAnnotations

        server = Server("weather-server")

        @server.list_tools()
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name="get_weather",
                    description=(
                        "通过 Open-Meteo 获取指定城市的真实当前天气，"
                        "包括温度、体感温度、湿度、天气状况和风速。"
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": "string",
                                "minLength": 1,
                                "description": "城市名称，如北京、上海",
                            },
                            "unit": {
                                "type": "string",
                                "enum": ["celsius", "fahrenheit"],
                                "description": "温度单位",
                                "default": "celsius",
                            },
                        },
                        "required": ["city"],
                    },
                    annotations=ToolAnnotations(
                        title="实时天气查询",
                        readOnlyHint=True,
                        destructiveHint=False,
                        idempotentHint=True,
                        openWorldHint=True,
                    ),
                )
            ]

        @server.call_tool()
        async def call_tool(name: str, arguments: dict) -> Dict[str, Any]:
            if name != "get_weather":
                raise WeatherServiceError(f"未知工具: {name}")
            return await handle_get_weather(
                arguments.get("city", ""),
                arguments.get("unit", "celsius"),
            )

        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    except ImportError:
        print("MCP SDK 未安装，请先安装项目依赖")


if __name__ == "__main__":
    asyncio.run(main())
