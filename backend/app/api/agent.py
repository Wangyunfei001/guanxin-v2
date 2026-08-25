"""Agent API 模块。

提供对话管理、消息发送（SSE 流式）等接口。
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Literal

from pydantic import BaseModel

from app.config import settings
from app.core.deps import get_admin_user, get_current_user
from app.core.responses import success
from app.models.agent import AgentConfig, get_agent_config_store
from app.models.tenant import User
from app.services.conversation_store import get_conversation_store
from app.skills.registry import get_skill_registry
from app.skills.executor import ADMIN_ONLY_SKILLS
from app.core.checkpoints import delete_checkpoint_thread
from app.services.workflow_store import get_workflow_store, WorkflowConflictError
from app.workflows.engine import resolve_uncertain_workflow

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


class ResolveWorkflowRequest(BaseModel):
    action: Literal["mark_completed", "retry", "cancel"]
    result_summary: str = ""


def _workflow_response(run: dict) -> dict:
    return {
        "run_id": run["run_id"],
        "conversation_id": run["conversation_id"],
        "agent_id": run["agent_id"],
        "goal": run["goal"],
        "summary": run["summary"],
        "status": run["status"],
        "current_step_index": run["current_step_index"],
        "version": run["version"],
        "last_error": run["last_error"],
        "steps": [
            {
                key: step[key]
                for key in (
                    "step_id", "position", "title", "tool_name", "tool_category",
                    "risk", "status", "attempt_count", "result", "error",
                )
            }
            for step in run["steps"]
        ],
        "interrupts": [
            {
                key: item[key]
                for key in (
                    "interrupt_id", "step_id", "kind", "status", "payload",
                    "created_at", "updated_at",
                )
            }
            for item in run["interrupts"]
        ],
        "created_at": run["created_at"],
        "updated_at": run["updated_at"],
    }


async def _config_response(
    config: AgentConfig,
    user_role: str = "admin",
    *,
    user_id: str = "system",
) -> dict:
    registry = get_skill_registry()
    registry.register_all()
    skills = registry.list_metadata()
    if user_role != "admin":
        skills = [skill for skill in skills if skill["name"] not in ADMIN_ONLY_SKILLS]

    from app.mcp.server import get_mcp_server_manager

    servers = get_mcp_server_manager().list_servers()
    from app.agent.tool_catalog import build_tool_catalog, serialize_tool_specs

    catalog = await build_tool_catalog(
        config,
        tenant_id=config.tenant_id,
        user_id=user_id,
        user_role=user_role,
    )
    data = config.to_dict()
    data.update({
        "agent_mode": "supervisor",
        "available_models": settings.available_models_list,
        "api_base": settings.openai_api_base,
        "tools_count": len(catalog),
        "skills_count": len(skills),
        "available_tools": ["kb_retrieval", "web_search", "deep_research"],
        "available_tool_specs": serialize_tool_specs(catalog),
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
    run_ids = get_workflow_store().list_run_ids_for_conversation(
        conversation_id, user.tenant_id, user.user_id
    )
    deleted = conv_store.delete_conversation_for_user(
        conversation_id, user.tenant_id, user.user_id
    )
    if not deleted:
        return {"code": 4041, "message": "对话未找到", "data": None}
    for run_id in run_ids:
        await delete_checkpoint_thread(run_id)
    return success({"deleted": True})


@router.get("/workflows/{run_id}")
async def get_workflow(run_id: str, user: User = Depends(get_current_user)):
    run = get_workflow_store().get_run(run_id, user.tenant_id, user.user_id)
    if run is None:
        raise HTTPException(status_code=404, detail="工作流未找到")
    return success(_workflow_response(run))


@router.post("/workflows/{run_id}/cancel")
async def cancel_workflow(run_id: str, user: User = Depends(get_current_user)):
    store = get_workflow_store()
    run = store.get_run(run_id, user.tenant_id, user.user_id)
    if run is None:
        raise HTTPException(status_code=404, detail="工作流未找到")
    if not store.cancel(run_id):
        raise HTTPException(status_code=409, detail="当前工作流不能取消")
    await delete_checkpoint_thread(run_id)
    updated = store.get_run(run_id, user.tenant_id, user.user_id)
    snapshot = _workflow_response(updated or run)
    get_conversation_store().update_workflow_part(
        run["conversation_id"], run_id, snapshot
    )
    return success(snapshot)


@router.post("/workflows/{run_id}/resolve")
async def resolve_workflow(
    run_id: str,
    request: ResolveWorkflowRequest,
    user: User = Depends(get_current_user),
):
    store = get_workflow_store()
    run = store.get_run(run_id, user.tenant_id, user.user_id)
    if run is None:
        raise HTTPException(status_code=404, detail="工作流未找到")
    try:
        updated = await resolve_uncertain_workflow(
            run=run,
            action=request.action,
            result_summary=request.result_summary,
            tenant_id=user.tenant_id,
            user_id=user.user_id,
            user_role=user.role,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (ValueError, WorkflowConflictError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    snapshot = _workflow_response(updated)
    get_conversation_store().update_workflow_part(
        updated["conversation_id"], run_id, snapshot
    )
    return success(snapshot)


@router.get("/config")
async def get_agent_config(user: User = Depends(get_current_user)):
    """获取当前租户持久化 Agent 配置。"""
    store = get_agent_config_store()
    config = store.get_or_create_default(user.tenant_id)
    return success(await _config_response(config, user.role, user_id=user.user_id))


@router.put("/config")
async def update_agent_config(
    request: UpdateAgentConfigRequest,
    user: User = Depends(get_admin_user),
):
    """更新当前租户默认 Agent 配置（仅管理员）。"""
    model_aliases = {
        "deepseek-chat": "deepseek-v4-pro",
        "deepseek-reasoner": "deepseek-v4-pro",
    }
    normalized_model = model_aliases.get(request.model, request.model)
    if normalized_model not in settings.available_models_list:
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
    if not set(request.enabled_tools).issubset(
        {"kb_retrieval", "web_search", "deep_research"}
    ):
        raise HTTPException(status_code=422, detail="包含未知内置工具")

    from app.mcp.server import get_mcp_server_manager

    server_names = {item["name"] for item in get_mcp_server_manager().list_servers()}
    if not set(request.mcp_servers).issubset(server_names):
        raise HTTPException(status_code=422, detail="包含未知 MCP Server")

    store = get_agent_config_store()
    config = store.get_or_create_default(user.tenant_id)
    config.model = normalized_model
    config.temperature = request.temperature
    config.max_tokens = request.max_tokens
    config.system_prompt = request.system_prompt
    config.enabled_tools = request.enabled_tools
    config.enabled_skills = request.enabled_skills
    config.mcp_servers = request.mcp_servers
    store.save_config(config)
    return success(await _config_response(config, user.role, user_id=user.user_id))
