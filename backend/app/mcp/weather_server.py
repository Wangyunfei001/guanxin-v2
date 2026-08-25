"""天气查询 MCP Server（示例）。

演示如何使用 MCP SDK 创建一个标准的 MCP Server。
可通过 `python -m app.mcp.weather_server` 启动。
"""

import asyncio
import random
from typing import Any, Dict


async def handle_get_weather(
    city: str,
    unit: str = "celsius",
) -> Dict[str, Any]:
    """获取城市天气（模拟数据）。

    Args:
        city: 城市名称
        unit: 温度单位 (celsius | fahrenheit)

    Returns:
        天气信息字典
    """
    # 模拟天气数据
    temp_c = random.randint(-10, 35)
    conditions = ["晴", "多云", "阴", "小雨", "大雨", "雪", "雾"]
    condition = random.choice(conditions)
    humidity = random.randint(30, 90)
    wind_speed = random.randint(0, 30)

    if unit == "fahrenheit":
        temp = temp_c * 9 / 5 + 32
        temp_str = f"{temp:.1f}°F"
    else:
        temp_str = f"{temp_c}°C"

    return {
        "simulated": True,
        "notice": "演示模拟数据，不代表实时天气",
        "city": city,
        "temperature": temp_str,
        "condition": condition,
        "humidity": f"{humidity}%",
        "wind_speed": f"{wind_speed} km/h",
        "unit": unit,
    }


async def main() -> None:
    """MCP Server 主入口。"""
    try:
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        from mcp.types import Tool, TextContent, ToolAnnotations

        server = Server("weather-server")

        @server.list_tools()
        async def list_tools() -> list[Tool]:
            """列出可用工具。"""
            return [
                Tool(
                    name="get_weather",
                    description="获取指定城市的天气演示数据。结果为模拟数据，不代表实时天气。",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": "string",
                                "description": "城市名称，如北京、上海",
                            },
                            "unit": {
                                "type": "string",
                                "description": "温度单位：celsius 或 fahrenheit",
                                "default": "celsius",
                            },
                        },
                        "required": ["city"],
                    },
                    annotations=ToolAnnotations(
                        title="天气演示查询",
                        readOnlyHint=True,
                        destructiveHint=False,
                        idempotentHint=False,
                        openWorldHint=False,
                    ),
                )
            ]

        @server.call_tool()
        async def call_tool(
            name: str, arguments: dict
        ) -> list[TextContent]:
            """处理工具调用。"""
            if name == "get_weather":
                city = arguments.get("city", "未知")
                unit = arguments.get("unit", "celsius")
                result = await handle_get_weather(city, unit)
                import json

                return [
                    TextContent(
                        type="text",
                        text=json.dumps(result, ensure_ascii=False, indent=2),
                    )
                ]
            else:
                return [
                    TextContent(
                        type="text",
                        text=f"未知工具: {name}",
                    )
                ]

        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    except ImportError:
        # MCP SDK 未安装时的回退
        import json

        # 直接运行一次天气查询作为演示
        result = await handle_get_weather("北京")
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
