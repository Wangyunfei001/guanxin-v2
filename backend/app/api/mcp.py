"""MCP API 模块。

提供 MCP Server 管理、连接测试、工具调用等接口。
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.deps import get_admin_user, get_current_user
from app.core.responses import success
from app.mcp.client import get_mcp_client
from app.mcp.server import get_mcp_server_manager
from app.models.tenant import User

router = APIRouter(prefix="/mcp", tags=["MCP"])


@router.get("/servers")
async def list_servers(user: User = Depends(get_current_user)):
    """列出所有 MCP Server 配置。"""
    manager = get_mcp_server_manager()
    return success(manager.list_servers())


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
    return success(result)


@router.get("/connections")
async def list_connections(user: User = Depends(get_current_user)):
    """列出所有 MCP 连接。"""
    client = get_mcp_client()
    return success(client.list_connections())


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
    """调用 MCP Server 上的工具。"""
    client = get_mcp_client()
    result = await client.call_tool(
        server_name=request.server_name,
        tool_name=request.tool_name,
        arguments=request.arguments,
    )
    return success(result)
