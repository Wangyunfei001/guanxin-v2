"""真实天气 MCP Server 测试。"""

import sys
from typing import Callable

import httpx
import pytest

from app.mcp.client import MCPClient
from app.mcp.weather_server import (
    FORECAST_URL,
    GEOCODING_URL,
    WeatherServiceError,
    describe_weather_code,
    handle_get_weather,
)


def _location_payload() -> dict:
    return {
        "results": [
            {
                "name": "北京",
                "latitude": 39.9075,
                "longitude": 116.39723,
                "timezone": "Asia/Shanghai",
                "admin1": "北京市",
                "country": "中国",
            }
        ]
    }


def _weather_payload(unit: str = "celsius", code: int = 96) -> dict:
    is_fahrenheit = unit == "fahrenheit"
    return {
        "timezone": "Asia/Shanghai",
        "current_units": {
            "temperature_2m": "°F" if is_fahrenheit else "°C",
            "relative_humidity_2m": "%",
            "apparent_temperature": "°F" if is_fahrenheit else "°C",
            "weather_code": "wmo code",
            "wind_speed_10m": "km/h",
        },
        "current": {
            "time": "2026-08-25T13:45",
            "temperature_2m": 81.9 if is_fahrenheit else 27.7,
            "relative_humidity_2m": 82,
            "apparent_temperature": 92.3 if is_fahrenheit else 33.5,
            "weather_code": code,
            "wind_speed_10m": 3.4,
        },
    }


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_weather_mcp_exposes_compatible_read_only_schema() -> None:
    result = await MCPClient().connect(
        "weather-test",
        sys.executable,
        ["-m", "app.mcp.weather_server"],
    )

    assert result["status"] == "connected"
    tool = result["tools"][0]
    assert tool["name"] == "get_weather"
    assert tool["input_schema"]["required"] == ["city"]
    assert tool["input_schema"]["properties"]["unit"]["enum"] == [
        "celsius",
        "fahrenheit",
    ]
    assert tool["annotations"]["readOnlyHint"] is True
    assert tool["annotations"]["openWorldHint"] is True


@pytest.mark.asyncio
async def test_get_weather_returns_real_structured_data() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if str(request.url).startswith(GEOCODING_URL):
            return httpx.Response(200, json=_location_payload())
        return httpx.Response(200, json=_weather_payload())

    async with _client(handler) as client:
        result = await handle_get_weather("  北京  ", client=client)

    assert result == {
        "simulated": False,
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
        "condition": "雷暴伴小冰雹",
        "weather_code": 96,
        "humidity": "82%",
        "wind_speed": "3.4 km/h",
        "unit": "celsius",
    }
    assert requests[0].url.params["name"] == "北京"
    assert requests[0].url.params["language"] == "zh"
    assert requests[1].url.params["latitude"] == "39.9075"
    assert requests[1].url.params["longitude"] == "116.39723"
    assert requests[1].url.params["timezone"] == "Asia/Shanghai"
    assert requests[1].url.params["temperature_unit"] == "celsius"


@pytest.mark.asyncio
async def test_get_weather_uses_provider_fahrenheit_unit() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if str(request.url).startswith(GEOCODING_URL):
            return httpx.Response(200, json=_location_payload())
        return httpx.Response(200, json=_weather_payload("fahrenheit"))

    async with _client(handler) as client:
        result = await handle_get_weather("北京", "fahrenheit", client)

    assert requests[1].url.params["temperature_unit"] == "fahrenheit"
    assert result["temperature"] == "81.9°F"
    assert result["apparent_temperature"] == "92.3°F"
    assert result["unit"] == "fahrenheit"


def test_weather_code_has_safe_fallback() -> None:
    assert describe_weather_code(0) == "晴"
    assert describe_weather_code(96) == "雷暴伴小冰雹"
    assert describe_weather_code(404) == "未知天气（WMO 404）"


@pytest.mark.asyncio
async def test_get_weather_rejects_invalid_arguments() -> None:
    with pytest.raises(WeatherServiceError, match="城市名称不能为空"):
        await handle_get_weather(" ")
    with pytest.raises(WeatherServiceError, match="温度单位仅支持"):
        await handle_get_weather("北京", "kelvin")


@pytest.mark.asyncio
async def test_get_weather_reports_unknown_city() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"generationtime_ms": 0.1})

    async with _client(handler) as client:
        with pytest.raises(WeatherServiceError, match="未找到城市"):
            await handle_get_weather("不存在的城市", client=client)


@pytest.mark.asyncio
async def test_get_weather_reports_timeout_without_fake_fallback() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("upstream timeout", request=request)

    async with _client(handler) as client:
        with pytest.raises(WeatherServiceError, match="请求超时"):
            await handle_get_weather("北京", client=client)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["http", "json", "missing"])
async def test_get_weather_reports_upstream_failures(failure: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).startswith(GEOCODING_URL):
            if failure == "http":
                return httpx.Response(503, json={"reason": "unavailable"})
            if failure == "json":
                return httpx.Response(200, content=b"not-json")
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "name": "北京",
                            "latitude": 39.9075,
                            "timezone": "Asia/Shanghai",
                        }
                    ]
                },
            )
        raise AssertionError("畸形位置数据不应继续请求天气接口")

    async with _client(handler) as client:
        with pytest.raises(WeatherServiceError, match="天气服务"):
            await handle_get_weather("北京", client=client)
