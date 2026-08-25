"""MCP API 模块。

提供 MCP Server 管理、连接测试、工具调用等接口。
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.deps import get_admin_user, get_current_user
from app.core.responses import success
from app.mcp.client import get_mcp_client
from app.mcp.server import get_mcp_server_manager
from app.models.agent import get_agent_config_store
from app.models.tenant import User
from app.services.mcp_policy_store import get_mcp_tool_policy_store

router = APIRouter(prefix="/mcp", tags=["MCP"])


@router.get("/servers")
async def list_servers(user: User = Depends(get_current_user)):
    """列出所有 MCP Server 配置。"""
    manager = get_mcp_server_manager()
    client = get_mcp_client()
    config = get_agent_config_store().get_or_create_default(user.tenant_id)
    servers = []
    for server in manager.list_servers():
        connection = client.get_connection(server["name"])
        servers.append(
            {
                **server,
                "registered": True,
                "runtime_status": (
                    connection.get("status", "disconnected")
                    if connection
                    else "disconnected"
                ),
                "agent_enabled": server["name"] in config.mcp_servers,
            }
        )
    return success(servers)


class RegisterServerRequest(BaseModel):
    """注册 MCP Server 请求。"""

    name: str
    command: str
    args: List[str] = []
    env: Dict[str, str] = {}
    description: str = ""


@router.post("/servers")
async def register_server(
    request: RegisterServerRequest,
    user: User = Depends(get_admin_user),
):
    """注册 MCP Server。"""
    manager = get_mcp_server_manager()
    config = manager.register_server(
        name=request.name,
        command=request.command,
        args=request.args,
        env=request.env,
        description=request.description,
    )
    return success(config)


@router.delete("/servers/{server_name}")
async def unregister_server(
    server_name: str,
    user: User = Depends(get_admin_user),
):
    """注销 MCP Server。"""
    manager = get_mcp_server_manager()
    deleted = manager.unregister_server(server_name)
    if not deleted:
        return {"code": 4041, "message": "服务器未找到", "data": None}
    get_mcp_client().disconnect(server_name)
    agent_store = get_agent_config_store()
    config = agent_store.get_or_create_default(user.tenant_id)
    if server_name in config.mcp_servers:
        config.mcp_servers = [item for item in config.mcp_servers if item != server_name]
        agent_store.save_config(config)
    get_mcp_tool_policy_store().delete_server(user.tenant_id, server_name)
    return success({"deleted": True})


class ConnectRequest(BaseModel):
    """连接 MCP Server 请求。"""

    server_name: str


@router.post("/connect")
async def connect_server(
    request: ConnectRequest,
    user: User = Depends(get_admin_user),
):
    """连接到 MCP Server。"""
    manager = get_mcp_server_manager()
    config = manager.get_server(request.server_name)
    if config is None:
        return {"code": 4041, "message": "服务器配置未找到", "data": None}

    client = get_mcp_client()
    result = await client.connect(
        server_name=config["name"],
        command=config["command"],
        args=config["args"],
        env=config.get("env"),
    )
    if result.get("status") == "connected":
        agent_store = get_agent_config_store()
        agent_config = agent_store.get_or_create_default(user.tenant_id)
        if request.server_name not in agent_config.mcp_servers:
            agent_config.mcp_servers = [*agent_config.mcp_servers, request.server_name]
            agent_store.save_config(agent_config)

        policy_store = get_mcp_tool_policy_store()
        tools = []
        for tool in result.get("tools", []):
            default_read = request.server_name == "weather" and tool.get("name") == "get_weather"
            policy = policy_store.ensure(
                user.tenant_id,
                request.server_name,
                tool.get("name", ""),
                effect="read" if default_read else "unknown",
                approval_required=not default_read,
                metadata={"annotations": tool.get("annotations", {})},
            )
            tools.append({**tool, "policy": policy})
        result["tools"] = tools
        result["agent_enabled"] = True
    return success(result)


@router.get("/connections")
async def list_connections(user: User = Depends(get_current_user)):
    """列出所有 MCP 连接。"""
    client = get_mcp_client()
    policy_store = get_mcp_tool_policy_store()
    config = get_agent_config_store().get_or_create_default(user.tenant_id)
    connections = []
    for connection in client.list_connections():
        tools = []
        for tool in connection.get("tools", []):
            policy = policy_store.get(
                user.tenant_id, connection["server_name"], tool.get("name", "")
            )
            tools.append({**tool, "policy": policy})
        connections.append(
            {
                **connection,
                "tools": tools,
                "agent_enabled": connection["server_name"] in config.mcp_servers,
            }
        )
    return success(connections)


class ToolPolicyRequest(BaseModel):
    enabled: bool = True
    effect: str
    approval_required: bool = True


@router.put("/servers/{server_name}/tools/{tool_name}/policy")
async def update_tool_policy(
    server_name: str,
    tool_name: str,
    request: ToolPolicyRequest,
    user: User = Depends(get_admin_user),
):
    """Classify a discovered MCP tool for the current tenant."""
    if request.effect not in {"read", "write", "unknown"}:
        raise HTTPException(status_code=422, detail="effect 必须是 read、write 或 unknown")
    connection = get_mcp_client().get_connection(server_name)
    if connection is None or not any(
        item.get("name") == tool_name for item in connection.get("tools", [])
    ):
        raise HTTPException(status_code=404, detail="MCP 工具未发现")
    policy = get_mcp_tool_policy_store().save(
        user.tenant_id,
        server_name,
        tool_name,
        enabled=request.enabled,
        effect=request.effect,
        approval_required=request.approval_required,
    )
    return success(policy)


class CallToolRequest(BaseModel):
    """调用 MCP 工具请求。"""

    server_name: str
    tool_name: str
    arguments: Dict[str, Any] = {}


@router.post("/call-tool")
async def call_tool(
    request: CallToolRequest,
    user: User = Depends(get_current_user),
):
    """Directly invoke an enabled read-only MCP tool for the current tenant."""
    client = get_mcp_client()
    config = get_agent_config_store().get_or_create_default(user.tenant_id)
    if request.server_name not in config.mcp_servers:
        raise HTTPException(status_code=403, detail="当前 Agent 未启用该 MCP Server")
    available = await client.ensure_available(request.server_name)
    if available.get("status") != "connected":
        raise HTTPException(status_code=503, detail="MCP Server 当前不可用")
    policy = get_mcp_tool_policy_store().get(
        user.tenant_id,
        request.server_name,
        request.tool_name,
    )
    if (
        policy is None
        or not policy.get("enabled")
        or policy.get("effect") != "read"
        or policy.get("approval_required")
    ):
        raise HTTPException(status_code=403, detail="该工具不是已授权的只读能力")
    result = await client.call_tool(
        server_name=request.server_name,
        tool_name=request.tool_name,
        arguments=request.arguments,
    )
    return success(result)
