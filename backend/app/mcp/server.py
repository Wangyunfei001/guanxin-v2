"""MCP Server 模块。

提供 MCP Server 的启动和管理。
"""

import sys
from typing import Any, Dict, List, Optional


class MCPServerManager:
    """MCP Server 管理器：管理已注册的 MCP Server 配置。"""

    def __init__(self) -> None:
        self._servers: Dict[str, dict] = {}

    def register_server(
        self,
        name: str,
        command: str,
        args: List[str],
        env: Optional[Dict[str, str]] = None,
        description: str = "",
    ) -> dict:
        """注册 MCP Server 配置。"""
        config = {
            "name": name,
            "command": command,
            "args": args,
            "env": env or {},
            "description": description,
            "status": "registered",
        }
        self._servers[name] = config
        return config

    def unregister_server(self, name: str) -> bool:
        """注销 MCP Server。"""
        if name in self._servers:
            del self._servers[name]
            return True
        return False

    def get_server(self, name: str) -> Optional[dict]:
        """获取 MCP Server 配置。"""
        return self._servers.get(name)

    def list_servers(self) -> List[dict]:
        """列出所有 MCP Server。"""
        return list(self._servers.values())

    def init_default_servers(self) -> None:
        """初始化默认 MCP Server 配置。"""
        if not self._servers:
            self.register_server(
                name="weather",
                command=sys.executable,
                args=["-m", "app.mcp.weather_server"],
                description="天气查询 MCP Server（示例）",
            )


# 全局单例
_mcp_server_manager: Optional[MCPServerManager] = None


def get_mcp_server_manager() -> MCPServerManager:
    """获取全局 MCP Server 管理器单例。"""
    global _mcp_server_manager
    if _mcp_server_manager is None:
        _mcp_server_manager = MCPServerManager()
        _mcp_server_manager.init_default_servers()
    return _mcp_server_manager
