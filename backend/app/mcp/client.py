"""MCP 客户端模块。

负责与外部 MCP Server 建立连接、调用工具。

连接缓存按租户隔离：不同租户可以有同名但不同命令行的 MCP Server，
互不覆盖。工具定义只对所属租户可见。
"""

import asyncio
import json
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

# (tenant_id, server_name) -> 连接信息
ConnectionKey = Tuple[str, str]

# 单次 MCP 握手 / 工具调用的超时。挂死的 Server 不能永久占住请求。
MCP_CALL_TIMEOUT = timedelta(seconds=30)
MCP_CALL_TIMEOUT_SECONDS = MCP_CALL_TIMEOUT.total_seconds()


class MCPClient:
    """MCP 客户端：管理与 MCP Server 的连接。"""

    def __init__(self) -> None:
        self._connections: Dict[ConnectionKey, dict] = {}

    async def connect(
        self,
        tenant_id: str,
        server_name: str,
        command: str,
        args: List[str],
        env: Optional[Dict[str, str]] = None,
    ) -> dict:
        """连接到 MCP Server。

        Args:
            tenant_id: 所属租户
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
                async with ClientSession(
                    read, write, read_timeout_seconds=MCP_CALL_TIMEOUT
                ) as session:
                    await asyncio.wait_for(
                        session.initialize(), timeout=MCP_CALL_TIMEOUT_SECONDS
                    )

                    # 获取工具列表
                    tools_result = await asyncio.wait_for(
                        session.list_tools(), timeout=MCP_CALL_TIMEOUT_SECONDS
                    )
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

                    self._connections[(tenant_id, server_name)] = {
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

    async def ensure_available(self, tenant_id: str, server_name: str) -> dict:
        """Discover a registered server on demand after process restarts."""
        current = self._connections.get((tenant_id, server_name))
        if current and current.get("status") == "connected":
            return {
                "server_name": server_name,
                "status": "connected",
                "tools": current.get("tools", []),
            }

        from app.mcp.server import get_mcp_server_manager

        config = get_mcp_server_manager().get_server(tenant_id, server_name)
        if config is None:
            return {
                "server_name": server_name,
                "status": "error",
                "error": "服务器配置未找到",
            }
        return await self.connect(
            tenant_id=tenant_id,
            server_name=config["name"],
            command=config["command"],
            args=config["args"],
            env=config.get("env"),
        )

    async def call_tool(
        self,
        tenant_id: str,
        server_name: str,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> dict:
        """调用 MCP Server 上的工具。

        Args:
            tenant_id: 所属租户
            server_name: 服务器名称
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            工具调用结果
        """
        conn = self._connections.get((tenant_id, server_name))
        if not conn:
            ensured = await self.ensure_available(tenant_id, server_name)
            if ensured.get("status") != "connected":
                return {
                    "success": False,
                    "error": ensured.get("error") or f"服务器 {server_name} 未连接",
                }
            conn = self._connections.get((tenant_id, server_name))
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
                async with ClientSession(
                    read, write, read_timeout_seconds=MCP_CALL_TIMEOUT
                ) as session:
                    await asyncio.wait_for(
                        session.initialize(), timeout=MCP_CALL_TIMEOUT_SECONDS
                    )
                    result = await asyncio.wait_for(
                        session.call_tool(tool_name, arguments),
                        timeout=MCP_CALL_TIMEOUT_SECONDS,
                    )
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

        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"MCP Server {server_name} 响应超时（{MCP_CALL_TIMEOUT_SECONDS} 秒）",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_connections(self, tenant_id: str) -> List[dict]:
        """列出当前租户的所有连接。"""
        return [
            {
                "server_name": name,
                "status": conn["status"],
                "tools": conn["tools"],
                "command": conn["command"],
                "args": conn["args"],
            }
            for (owner, name), conn in self._connections.items()
            if owner == tenant_id
        ]

    def get_connection(self, tenant_id: str, server_name: str) -> Optional[dict]:
        """获取当前租户的连接信息。"""
        return self._connections.get((tenant_id, server_name))

    def disconnect(self, tenant_id: str, server_name: str) -> bool:
        """断开当前租户的连接。"""
        key = (tenant_id, server_name)
        if key in self._connections:
            del self._connections[key]
            return True
        return False

    def get_tool_definitions(self, tenant_id: str) -> List[dict]:
        """获取当前租户已连接 MCP Server 的工具定义列表。

        返回格式适配 LangChain tool 注册，每个工具包含：
        - server_name: 所属 MCP Server 名称
        - tool_name: 工具原始名称
        - full_name: 完整工具名（mcp__<server>__<tool>）
        - description: 工具描述
        - input_schema: 输入参数 schema
        """
        definitions = []
        for (owner, server_name), conn in self._connections.items():
            if owner != tenant_id:
                continue
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
