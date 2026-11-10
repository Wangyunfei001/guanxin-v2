"""MCP Server 模块。

管理已注册的 MCP Server 配置。注册表按租户隔离：每个租户有独立的
Server 命名空间，任意租户的管理员只能注册、查看和注销自己租户的
Server，不会影响其他租户的 Agent。
"""

import sys
from typing import Dict, List, Optional, Tuple

# (tenant_id, server_name) -> 配置
ServerKey = Tuple[str, str]


class MCPServerManager:
    """MCP Server 管理器：管理各租户已注册的 MCP Server 配置。"""

    def __init__(self) -> None:
        self._servers: Dict[ServerKey, dict] = {}

    def register_server(
        self,
        tenant_id: str,
        name: str,
        command: str,
        args: List[str],
        env: Optional[Dict[str, str]] = None,
        description: str = "",
    ) -> dict:
        """注册（或覆盖）当前租户的 MCP Server 配置。"""
        config = {
            "name": name,
            "command": command,
            "args": args,
            "env": env or {},
            "description": description,
            "status": "registered",
        }
        self._servers[(tenant_id, name)] = config
        return config

    def unregister_server(self, tenant_id: str, name: str) -> bool:
        """注销当前租户的 MCP Server；不影响其他租户的同名 Server。"""
        key = (tenant_id, name)
        if key in self._servers:
            del self._servers[key]
            return True
        return False

    def get_server(self, tenant_id: str, name: str) -> Optional[dict]:
        """获取当前租户的 MCP Server 配置。"""
        return self._servers.get((tenant_id, name))

    def list_servers(self, tenant_id: str) -> List[dict]:
        """列出当前租户的全部 MCP Server 配置。"""
        return [
            config
            for (owner, _name), config in self._servers.items()
            if owner == tenant_id
        ]

    def init_default_servers(self, tenant_id: str) -> None:
        """为指定租户初始化默认 MCP Server 配置。"""
        from app.seed.data import SEED_MCP_SERVERS

        for config in SEED_MCP_SERVERS:
            if self.get_server(tenant_id, config["name"]) is None:
                self.register_server(
                    tenant_id=tenant_id,
                    name=config["name"],
                    command=config["command"],
                    args=config["args"],
                    env=config.get("env", {}),
                    description=config.get("description", ""),
                )


# 全局单例
_mcp_server_manager: Optional[MCPServerManager] = None


def get_mcp_server_manager() -> MCPServerManager:
    """获取全局 MCP Server 管理器单例。

    默认 Server 由 ``app.seed.init_data`` 按租户注册，不在这里自动写入——
    单例本身不知道当前租户是谁。
    """
    global _mcp_server_manager
    if _mcp_server_manager is None:
        _mcp_server_manager = MCPServerManager()
    return _mcp_server_manager
