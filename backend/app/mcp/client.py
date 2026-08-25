"""MCP 客户端模块。

负责与外部 MCP Server 建立连接、调用工具。
"""

import json
from typing import Any, Dict, List, Optional


class MCPClient:
    """MCP 客户端：管理与 MCP Server 的连接。"""

    def __init__(self) -> None:
        self._connections: Dict[str, dict] = {}  # key: server_name

    async def connect(
        self,
        server_name: str,
        command: str,
        args: List[str],
        env: Optional[Dict[str, str]] = None,
    ) -> dict:
        """连接到 MCP Server。

        Args:
            server_name: 服务器名称
            command: 启动命令（如 python）
            args: 命令参数列表
            env: 环境变量

        Returns:
            连接信息，包含可用工具列表
        """
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            server_params = StdioServerParameters(
                command=command,
                args=args,
                env=env,
            )

            # 使用 stdio_client 建立连接
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    # 获取工具列表
                    tools_result = await session.list_tools()
                    tools = []
                    for item in tools_result.tools:
                        annotations = getattr(item, "annotations", None)
                        tools.append(
                            {
                                "name": item.name,
                                "description": item.description or "",
                                "input_schema": getattr(item, "inputSchema", {}) or {},
                                "output_schema": getattr(item, "outputSchema", None),
                                "annotations": (
                                    annotations.model_dump(exclude_none=True)
                                    if annotations is not None
                                    else {}
                                ),
                                "metadata": getattr(item, "meta", None) or {},
                            }
                        )

                    self._connections[server_name] = {
                        "command": command,
                        "args": args,
                        "env": env,
                        "tools": tools,
                        "status": "connected",
                    }

                    return {
                        "server_name": server_name,
                        "status": "connected",
                        "tools": tools,
                    }

        except ImportError:
            return {
                "server_name": server_name,
                "status": "error",
                "error": "MCP SDK 未安装，请安装 mcp 包",
            }
        except Exception as e:
            return {
                "server_name": server_name,
                "status": "error",
                "error": str(e),
            }

    async def ensure_available(self, server_name: str) -> dict:
        """Discover a registered server on demand after process restarts."""
        current = self._connections.get(server_name)
        if current and current.get("status") == "connected":
            return {
                "server_name": server_name,
                "status": "connected",
                "tools": current.get("tools", []),
            }

        from app.mcp.server import get_mcp_server_manager

        config = get_mcp_server_manager().get_server(server_name)
        if config is None:
            return {
                "server_name": server_name,
                "status": "error",
                "error": "服务器配置未找到",
            }
        return await self.connect(
            server_name=config["name"],
            command=config["command"],
            args=config["args"],
            env=config.get("env"),
        )

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> dict:
        """调用 MCP Server 上的工具。

        Args:
            server_name: 服务器名称
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            工具调用结果
        """
        conn = self._connections.get(server_name)
        if not conn:
            ensured = await self.ensure_available(server_name)
            if ensured.get("status") != "connected":
                return {
                    "success": False,
                    "error": ensured.get("error") or f"服务器 {server_name} 未连接",
                }
            conn = self._connections.get(server_name)
        if not conn:
            return {"success": False, "error": f"服务器 {server_name} 未连接"}

        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            server_params = StdioServerParameters(
                command=conn["command"],
                args=conn["args"],
                env=conn.get("env"),
            )

            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    structured = getattr(result, "structuredContent", None)
                    output: Any = structured
                    if output is None:
                        texts = [
                            getattr(item, "text", "")
                            for item in (result.content or [])
                            if getattr(item, "text", "")
                        ]
                        joined = "\n".join(texts)
                        try:
                            output = json.loads(joined) if joined else ""
                        except json.JSONDecodeError:
                            output = joined
                    is_error = bool(getattr(result, "isError", False))
                    return {
                        "success": True,
                        "output": output,
                        "is_error": is_error,
                    }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_connections(self) -> List[dict]:
        """列出所有连接。"""
        return [
            {
                "server_name": name,
                "status": conn["status"],
                "tools": conn["tools"],
                "command": conn["command"],
                "args": conn["args"],
            }
            for name, conn in self._connections.items()
        ]

    def get_connection(self, server_name: str) -> Optional[dict]:
        """获取连接信息。"""
        return self._connections.get(server_name)

    def disconnect(self, server_name: str) -> bool:
        """断开连接。"""
        if server_name in self._connections:
            del self._connections[server_name]
            return True
        return False

    def get_tool_definitions(self) -> List[dict]:
        """获取所有已连接 MCP Server 的工具定义列表。

        返回格式适配 LangChain tool 注册，每个工具包含：
        - server_name: 所属 MCP Server 名称
        - tool_name: 工具原始名称
        - full_name: 完整工具名（mcp__<server>__<tool>）
        - description: 工具描述
        - input_schema: 输入参数 schema
        """
        definitions = []
        for server_name, conn in self._connections.items():
            for tool_info in conn.get("tools", []):
                definitions.append(
                    {
                        "server_name": server_name,
                        "tool_name": tool_info["name"],
                        "full_name": f"mcp__{server_name}__{tool_info['name']}",
                        "description": tool_info.get("description", ""),
                        "input_schema": tool_info.get("input_schema", {}),
                        "output_schema": tool_info.get("output_schema"),
                        "annotations": tool_info.get("annotations", {}),
                        "metadata": tool_info.get("metadata", {}),
                    }
                )
        return definitions


# 全局单例
_mcp_client: Optional[MCPClient] = None


def get_mcp_client() -> MCPClient:
    """获取全局 MCP 客户端单例。"""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client
