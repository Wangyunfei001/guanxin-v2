"""Agent API 模块。

提供对话管理、消息发送（SSE 流式）等接口。
"""

import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent.executor import execute_agent
from app.config import settings
from app.agent.prompts import DEFAULT_SYSTEM_PROMPT
from app.core.deps import get_current_user
from app.core.responses import success
from app.core.tenant import get_tenant_id
from app.models.agent import ConversationMessage
from app.models.tenant import User
from app.services.conversation_store import get_conversation_store
from app.skills.registry import get_skill_registry

router = APIRouter(prefix="/agent", tags=["Agent"])


class CreateConversationRequest(BaseModel):
    """创建对话请求。"""

    agent_id: str = "default"
    title: str = ""


class SendMessageRequest(BaseModel):
    """发送消息请求。"""

    conversation_id: str
    message: str
    agent_id: str = "default"
    system_prompt: str = ""
    enabled_tools: Optional[list[str]] = None
    model_name: str = ""
    temperature: float = 0.7


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
    conv = conv_store.get_conversation(conversation_id, user.tenant_id)
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
    deleted = conv_store.delete_conversation(conversation_id, user.tenant_id)
    if not deleted:
        return {"code": 4041, "message": "对话未找到", "data": None}
    return success({"deleted": True})


@router.get("/config")
async def get_agent_config(user: User = Depends(get_current_user)):
    """获取 Agent 运行时配置（只读）。"""
    registry = get_skill_registry()
    registry.register_all()

    skills = registry.list_skills()

    # Count tools: kb_retrieval + each skill as a tool
    tools_count = 1 + len(skills)  # 1 for kb_retrieval

    return success({
        "model": settings.openai_model,
        "temperature": settings.openai_temperature,
        "system_prompt": DEFAULT_SYSTEM_PROMPT,
        "agent_mode": settings.agent_mode,
        "available_models": settings.available_models_list,
        "api_base": settings.openai_api_base,
        "tools_count": tools_count,
        "skills_count": len(skills),
    })


@router.post("/chat")
async def chat(
    request: SendMessageRequest,
    user: User = Depends(get_current_user),
):
    """发送消息并获取流式响应（SSE）。"""
    tenant_id = get_tenant_id() or user.tenant_id

    # 确保对话存在
    conv_store = get_conversation_store()
    conv = conv_store.get_conversation(request.conversation_id, tenant_id)
    if conv is None:
        # 自动创建
        conv = conv_store.create_conversation(
            tenant_id=tenant_id,
            user_id=user.user_id,
            agent_id=request.agent_id,
            title=request.message[:20],
        )
        request.conversation_id = conv.conversation_id

    return StreamingResponse(
        execute_agent(
            user_message=request.message,
            conversation_id=request.conversation_id,
            tenant_id=tenant_id,
            user_id=user.user_id,
            agent_id=request.agent_id,
            system_prompt=request.system_prompt,
            enabled_tools=request.enabled_tools,
            model_name=request.model_name,
            temperature=request.temperature,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
