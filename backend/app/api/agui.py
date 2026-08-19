"""AG-UI 协议端点。

将 assistant-ui 前端的 AG-UI 协议请求转换为对现有 execute_agent() 的调用，
并把 SSE 输出转译为 AG-UI 事件流。

事件映射：
  SSE token            → AG-UI TEXT_MESSAGE_START (首个) + TEXT_MESSAGE_CONTENT
  SSE done             → AG-UI TEXT_MESSAGE_END + RUN_FINISHED
  SSE tool_call        → AG-UI TOOL_CALL_START + TOOL_CALL_ARGS
  SSE tool_result      → AG-UI TOOL_CALL_END
  SSE error            → AG-UI RUN_ERROR
"""

import json
import logging
import uuid
from typing import AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.agent.executor import execute_agent
from app.core.tenant import get_tenant_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["AG-UI"])


def entities_to_fields(entities: dict) -> list:
    """将 confirm_required 的 entities 转成表单字段列表。
    
    自动从LLM回复文本中解析字段信息（如果entities为空则返回空列表）。
    """
    fields = []
    for key, value in entities.items():
        if isinstance(value, dict):
            fields.append({
                "name": key,
                "label": value.get("label", key),
                "type": value.get("type", "text"),
                "required": value.get("required", False),
            })
        else:
            fields.append({
                "name": key,
                "label": str(value) if value else key,
                "type": "text",
                "required": False,
            })
    return fields


def _agui_event(event_type: str, **kwargs) -> str:
    """构建 AG-UI 协议事件（SSE 格式）。

    HttpAgent 使用 SSE parser：期望 data: 前缀 + 双换行分隔。
    """
    payload = {"type": event_type, **kwargs}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _stream_agui_response(
    input_body: dict,
    tenant_id: str,
    user_id: str,
) -> AsyncGenerator[str, None]:
    """将 RunAgentInput 转换为 AG-UI 事件流。

    Args:
        input_body: AG-UI RunAgentInput JSON
        tenant_id: 租户 ID
        user_id: 用户 ID
    """
    thread_id = input_body.get("threadId", str(uuid.uuid4()))
    run_id = input_body.get("runId", str(uuid.uuid4()))
    messages = input_body.get("messages", [])

    # 提取最后一条用户消息
    user_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_message = msg.get("content", "")
            break

    if not user_message:
        yield _agui_event(
            "RUN_ERROR",
            message="No user message found in input",
            code="NO_USER_MESSAGE",
        )
        return

    # 生成 conversation_id
    conversation_id = str(uuid.uuid4())
    agent_id = "default"

    message_id = str(uuid.uuid4())
    text_started = False
    # 追踪当前活跃的 tool_call，确保 TOOL_CALL_END 在 RUN_FINISHED 之前发送
    pending_tool_calls: Dict[str, str] = {}  # tool_call_id → tool_name

    # 发送 RUN_STARTED
    yield _agui_event(
        "RUN_STARTED",
        threadId=thread_id,
        runId=run_id,
    )

    try:
        async for sse_msg in execute_agent(
            user_message=user_message,
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            user_id=user_id or "anonymous",
            agent_id=agent_id,
            system_prompt="",
            enabled_tools=None,
            model_name="",
            temperature=0.7,
        ):
            # 解析 SSE 消息
            sse_str = sse_msg.strip()
            if not sse_str.startswith("data: "):
                continue
            try:
                data = json.loads(sse_str[6:])  # strip "data: " prefix
            except json.JSONDecodeError:
                continue

            event_subtype = data.get("type", "")

            if event_subtype == "token":
                content = data.get("content", "")
                if not content:
                    continue
                if not text_started:
                    yield _agui_event(
                        "TEXT_MESSAGE_START",
                        messageId=message_id,
                        role="assistant",
                    )
                    text_started = True
                yield _agui_event(
                    "TEXT_MESSAGE_CONTENT",
                    messageId=message_id,
                    delta=content,
                )

            elif event_subtype == "tool_call":
                tool_call_id = str(uuid.uuid4())
                tool_name = data.get("tool_name", "unknown")
                tool_input = data.get("tool_input", "")
                pending_tool_calls[tool_call_id] = tool_name
                yield _agui_event(
                    "TOOL_CALL_START",
                    toolCallId=tool_call_id,
                    toolCallName=tool_name,
                    parentMessageId=message_id,
                )
                yield _agui_event(
                    "TOOL_CALL_ARGS",
                    toolCallId=tool_call_id,
                    delta=tool_input,
                )

            elif event_subtype == "tool_result":
                # tool_result 不含 tool_call_id，关闭所有活跃的 tool call（顺序执行）
                for tid in list(pending_tool_calls.keys()):
                    yield _agui_event("TOOL_CALL_END", toolCallId=tid)
                    del pending_tool_calls[tid]

            elif event_subtype == "confirm_required":
                # agent 模式切换到 confirm，发射表单 CUSTOM 事件
                action_desc = data.get("action", "执行操作")
                entities = data.get("entities", {})
                yield _agui_event(
                    "CUSTOM",
                    name="confirm_form",
                    value={
                        "action": action_desc,
                        "fields": entities_to_fields(entities),
                    },
                )

            elif event_subtype == "a2ui":
                # A2UI schema 事件，映射为 CUSTOM 事件
                schema = data.get("schema")
                if schema:
                    yield _agui_event(
                        "CUSTOM",
                        name="a2ui",
                        value=schema,
                    )

            elif event_subtype == "done":
                # 关闭所有未完成的 tool call
                for tid in list(pending_tool_calls.keys()):
                    yield _agui_event("TOOL_CALL_END", toolCallId=tid)
                    del pending_tool_calls[tid]
                if text_started:
                    yield _agui_event(
                        "TEXT_MESSAGE_END",
                        messageId=message_id,
                    )
                yield _agui_event(
                    "RUN_FINISHED",
                    threadId=thread_id,
                    runId=run_id,
                )
                return

            elif event_subtype == "error":
                yield _agui_event(
                    "RUN_ERROR",
                    message=data.get("content", "Agent execution error"),
                )
                return

    except Exception as e:
        logger.exception("AG-UI stream error")
        yield _agui_event(
            "RUN_ERROR",
            message=str(e),
        )

    # 确保 RUN_FINISHED（兜底）
    for tid in list(pending_tool_calls.keys()):
        yield _agui_event("TOOL_CALL_END", toolCallId=tid)
    if text_started:
        yield _agui_event("TEXT_MESSAGE_END", messageId=message_id)
    yield _agui_event("RUN_FINISHED", threadId=thread_id, runId=run_id)


@router.post("/chat/agui")
async def chat_agui(request: Request):
    """AG-UI 协议聊天端点。

    接收 RunAgentInput JSON，返回 AG-UI 事件流。
    """
    body = await request.json()

    # 提取用户信息（从请求头或默认值）
    tenant_id = get_tenant_id() or "default"
    user_id = request.headers.get("X-User-Id", "anonymous")

    return StreamingResponse(
        _stream_agui_response(body, tenant_id, user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )