"""Agent API 模块。

提供对话管理、消息发送（SSE 流式）等接口。
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.core.deps import get_admin_user, get_current_user
from app.core.responses import success
from app.models.agent import AgentConfig, get_agent_config_store
from app.models.tenant import User
from app.services.conversation_store import get_conversation_store
from app.skills.registry import get_skill_registry
from app.skills.executor import ADMIN_ONLY_SKILLS

router = APIRouter(prefix="/agent", tags=["Agent"])


class CreateConversationRequest(BaseModel):
    """创建对话请求。"""

    agent_id: str = "default"
    title: str = ""


class UpdateAgentConfigRequest(BaseModel):
    """更新当前租户默认 Agent 配置。"""

    model: str
    temperature: float
    max_tokens: int
    system_prompt: str
    enabled_tools: list[str]
    enabled_skills: list[str]
    mcp_servers: list[str]


def _config_response(config: AgentConfig, user_role: str = "admin") -> dict:
    registry = get_skill_registry()
    registry.register_all()
    skills = registry.list_metadata()
    if user_role != "admin":
        skills = [skill for skill in skills if skill["name"] not in ADMIN_ONLY_SKILLS]

    from app.mcp.server import get_mcp_server_manager

    servers = get_mcp_server_manager().list_servers()
    data = config.to_dict()
    data.update({
        "agent_mode": settings.agent_mode,
        "available_models": settings.available_models_list,
        "api_base": settings.openai_api_base,
        "tools_count": 1 + len(skills),
        "skills_count": len(skills),
        "available_tools": ["kb_retrieval"],
        "available_skills": skills,
        "available_mcp_servers": [server["name"] for server in servers],
    })
    return data


@router.post("/conversations")
async def create_conversation(
    request: CreateConversationRequest,
    user: User = Depends(get_current_user),
):
    """创建新对话。"""
    conv_store = get_conversation_store()
    conv = conv_store.create_conversation(
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        agent_id=request.agent_id,
        title=request.title,
    )
    return success(conv.to_dict())


@router.get("/conversations")
async def list_conversations(user: User = Depends(get_current_user)):
    """列出对话。"""
    conv_store = get_conversation_store()
    convs = conv_store.list_conversations(user.tenant_id, user.user_id)
    return success([
        {
            "conversation_id": c.conversation_id,
            "title": c.title,
            "agent_id": c.agent_id,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
            "message_count": len(c.messages),
        }
        for c in convs
    ])


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
):
    """获取对话详情（含消息历史）。"""
    conv_store = get_conversation_store()
    conv = conv_store.get_conversation_for_user(
        conversation_id, user.tenant_id, user.user_id
    )
    if conv is None:
        return {"code": 4041, "message": "对话未找到", "data": None}
    return success(conv.to_dict())


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
):
    """删除对话。"""
    conv_store = get_conversation_store()
    deleted = conv_store.delete_conversation_for_user(
        conversation_id, user.tenant_id, user.user_id
    )
    if not deleted:
        return {"code": 4041, "message": "对话未找到", "data": None}
    return success({"deleted": True})


@router.get("/config")
async def get_agent_config(user: User = Depends(get_current_user)):
    """获取当前租户持久化 Agent 配置。"""
    store = get_agent_config_store()
    config = store.get_or_create_default(user.tenant_id)
    return success(_config_response(config, user.role))


@router.put("/config")
async def update_agent_config(
    request: UpdateAgentConfigRequest,
    user: User = Depends(get_admin_user),
):
    """更新当前租户默认 Agent 配置（仅管理员）。"""
    if request.model not in settings.available_models_list:
        raise HTTPException(status_code=422, detail="模型不在可用列表中")
    if not 0 <= request.temperature <= 2:
        raise HTTPException(status_code=422, detail="temperature 必须在 0 到 2 之间")
    if not 1 <= request.max_tokens <= 32768:
        raise HTTPException(status_code=422, detail="max_tokens 必须在 1 到 32768 之间")

    registry = get_skill_registry()
    registry.register_all()
    skill_names = {skill.name for skill in registry.list_skills()}
    if not set(request.enabled_skills).issubset(skill_names):
        raise HTTPException(status_code=422, detail="包含未知 Skill")
    if not set(request.enabled_tools).issubset({"kb_retrieval"}):
        raise HTTPException(status_code=422, detail="包含未知内置工具")

    from app.mcp.server import get_mcp_server_manager

    server_names = {item["name"] for item in get_mcp_server_manager().list_servers()}
    if not set(request.mcp_servers).issubset(server_names):
        raise HTTPException(status_code=422, detail="包含未知 MCP Server")

    store = get_agent_config_store()
    config = store.get_or_create_default(user.tenant_id)
    config.model = request.model
    config.temperature = request.temperature
    config.max_tokens = request.max_tokens
    config.system_prompt = request.system_prompt
    config.enabled_tools = request.enabled_tools
    config.enabled_skills = request.enabled_skills
    config.mcp_servers = request.mcp_servers
    store.save_config(config)
    return success(_config_response(config, user.role))
