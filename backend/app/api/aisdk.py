"""AI SDK 协议端点。

将 assistant-ui / AI SDK 前端的请求转换为对现有 execute_agent() 的调用，
并把 SSE 输出转译为 AI SDK Data Stream Protocol 事件流。

事件映射：
  SSE token (first)     → start + text-start + text-delta
  SSE token (subsequent) → text-delta
  SSE done              → text-end + finish + [DONE]
  SSE tool_call         → tool-input-start + tool-input-delta + tool-input-available
  SSE tool_result       → tool-output-available
  SSE a2ui              → data-a2ui
  SSE confirm_required  → tool-input-available (confirm_action) + tool-approval-request
  SSE error             → error + [DONE]

参考：https://ai-sdk.dev/docs/ai-sdk-core/stream-protocol
"""

import json
import logging
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.agent.confirmations import get_confirmation_entities
from app.agent.executor import execute_agent
from app.core.deps import get_current_user
from app.models.tenant import User
from app.models.skill_context import SkillContext
from app.services.approval_store import get_approval_store
from app.services.conversation_store import get_conversation_store
from app.skills.executor import SkillExecutor

logger = logging.getLogger(__name__)

def _find_approval_response(messages: list[dict]) -> Optional[dict]:
    """Find the latest AI SDK tool approval response in UI messages."""
    for message in reversed(messages):
        if message.get("role") != "assistant":
            continue
        for part in reversed(message.get("parts") or []):
            if not isinstance(part, dict) or not str(part.get("type", "")).startswith("tool-"):
                continue
            approval = part.get("approval")
            if (
                isinstance(approval, dict)
                and approval.get("id")
                and isinstance(approval.get("approved"), bool)
            ):
                return {
                    "approval_id": approval["id"],
                    "approved": approval["approved"],
                    "reason": approval.get("reason", ""),
                    "tool_call_id": part.get("toolCallId", ""),
                }
    return None


def _approval_params(reason: str) -> dict:
    if not reason:
        return {}
    try:
        value = json.loads(reason)
        return value if isinstance(value, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


async def _stream_approval_response(
    approval_response: dict,
    conversation_id: str,
    tenant_id: str,
    user_id: str,
    user_role: str,
) -> AsyncGenerator[str, None]:
    """Resolve and, when approved, consume an action exactly once."""
    approval_store = get_approval_store()
    approval = approval_store.respond(
        approval_response["approval_id"],
        conversation_id,
        approval_response["approved"],
        approval_response.get("reason", ""),
    )
    if approval is None:
        yield _aisdk_event("error", errorText="Approval not found")
        yield "data: [DONE]\n\n"
        return

    tool_call_id = approval["tool_call_id"]
    conv_store = get_conversation_store()
    if not approval_response["approved"]:
        conv_store.update_approval_part(
            conversation_id,
            approval["approval_id"],
            approved=False,
            reason=approval_response.get("reason", ""),
        )
        yield _aisdk_event("tool-output-denied", toolCallId=tool_call_id)
        yield _aisdk_event("finish-step")
        yield _aisdk_event("finish")
        yield "data: [DONE]\n\n"
        return

    claimed = approval_store.consume(approval["approval_id"], conversation_id)
    if claimed is None:
        # A retry after consumption returns the persisted result without executing again.
        yield _aisdk_event("finish-step")
        yield _aisdk_event("finish")
        yield "data: [DONE]\n\n"
        return

    intent_to_skill = {
        "single_create": "create_user",
        "single_update": "update_user",
        "single_delete": "delete_user",
        "batch_operation": "export_data",
    }
    intent_label = claimed["action"].get("intent_label", "")
    skill_name = intent_to_skill.get(intent_label)
    if not skill_name:
        result = {"success": False, "error": "Unsupported approved action"}
    elif user_role != "admin":
        result = {"success": False, "error": "权限不足：该操作仅管理员可执行"}
    else:
        params = _approval_params(claimed["action"].get("approval_reason", ""))
        result = SkillExecutor().execute(
            skill_name,
            params,
            SkillContext(
                tenant_id=tenant_id,
                user_id=user_id,
                user_role=user_role,
                conversation_id=conversation_id,
            ),
        ).to_dict()

    conv_store.update_approval_part(
        conversation_id,
        claimed["approval_id"],
        approved=True,
        reason=approval_response.get("reason", ""),
        output=result,
    )
    yield _aisdk_event(
        "tool-output-available",
        toolCallId=tool_call_id,
        output=result,
    )
    yield _aisdk_event("finish-step")
    yield _aisdk_event("finish")
    yield "data: [DONE]\n\n"


router = APIRouter(prefix="/agent", tags=["AI-SDK"])


def _aisdk_event(event_type: str, **kwargs) -> str:
    """构建 AI SDK Data Stream Protocol 事件（SSE 格式）。

    格式: data: {"type":"...",...}\n\n
    """
    payload = {"type": event_type, **kwargs}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _try_parse_json(raw: str) -> Any:
    """尝试将 JSON 字符串解析为 dict/list，失败则返回原始字符串。"""
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


async def _stream_aisdk_response(
    input_body: dict,
    tenant_id: str,
    user_id: str,
    user_role: str,
) -> AsyncGenerator[str, None]:
    """将 RunAgentInput 转换为 AI SDK Data Stream Protocol 事件流。

    Args:
        input_body: AI SDK UIMessage request JSON
        tenant_id: 租户 ID
        user_id: 用户 ID
    """
    messages = input_body.get("messages", [])

    approval_response = _find_approval_response(messages)
    if approval_response:
        async for event in _stream_approval_response(
            approval_response,
            input_body["id"],
            tenant_id,
            user_id,
            user_role,
        ):
            yield event
        return

    # 提取最后一条用户消息
    # AI SDK 格式: { role, parts: [{type:"text", text:"..."}] }
    # 兼容旧 content 字段，正式请求使用 parts。
    def _extract_user_text(msg: dict) -> str:
        parts = msg.get("parts") or []
        texts = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("type") == "text"]
        return "".join(texts) or msg.get("content", "")

    user_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_message = _extract_user_text(msg)
            break

    if not user_message:
        yield _aisdk_event("error", errorText="No user message found in input")
        yield "data: [DONE]\n\n"
        return

    # 生成唯一 ID
    message_id = f"msg_{uuid.uuid4().hex[:12]}"
    text_id = f"text_{uuid.uuid4().hex[:12]}"

    # 状态标志
    text_started = False
    message_started = False
    tracked_intent: str = ""
    # 追踪 tool_call → AI-SDK toolCallId 的映射（用于 tool_result 时回填）
    pending_tool_calls: Dict[str, str] = {}  # tool_name → toolCallId

    conversation_id = input_body["id"]

    agent_id = "default"

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
            user_role=user_role,
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

            # --- token ---
            if event_subtype == "token":
                content = data.get("content", "")
                if not content:
                    continue

                # 首个 token：发送 start + text-start
                if not message_started:
                    yield _aisdk_event("start", messageId=message_id)
                    message_started = True

                if not text_started:
                    yield _aisdk_event("text-start", id=text_id)
                    text_started = True

                yield _aisdk_event("text-delta", id=text_id, delta=content)

            # --- tool_call ---
            elif event_subtype == "tool_call":
                tool_call_id = data.get("tool_call_id") or f"call_{uuid.uuid4().hex[:12]}"
                tool_name = data.get("tool_name", "unknown")
                tool_input = data.get("tool_input", "")

                pending_tool_calls[tool_name] = tool_call_id

                # tool-input-start
                yield _aisdk_event(
                    "tool-input-start",
                    toolCallId=tool_call_id,
                    toolName=tool_name,
                )
                # tool-input-delta (stream raw input string)
                if tool_input:
                    yield _aisdk_event(
                        "tool-input-delta",
                        toolCallId=tool_call_id,
                        inputTextDelta=tool_input,
                    )
                # tool-input-available (with parsed input)
                parsed_input = _try_parse_json(tool_input)
                yield _aisdk_event(
                    "tool-input-available",
                    toolCallId=tool_call_id,
                    toolName=tool_name,
                    input=parsed_input if isinstance(parsed_input, dict) else {"raw": tool_input},
                )

            # --- tool_result ---
            elif event_subtype == "tool_result":
                tool_name = data.get("tool_name", "unknown")
                tool_output = data.get("tool_output", "")
                tool_call_id = data.get("tool_call_id") or pending_tool_calls.pop(
                    tool_name, f"call_{uuid.uuid4().hex[:12]}"
                )

                parsed_output = _try_parse_json(tool_output)
                yield _aisdk_event(
                    "tool-output-available",
                    toolCallId=tool_call_id,
                    output=parsed_output if isinstance(parsed_output, (dict, list)) else {"result": tool_output},
                )

            # --- a2ui ---
            elif event_subtype == "a2ui":
                schema = data.get("schema")
                if schema:
                    yield _aisdk_event(
                        "data-a2ui",
                        data={
                            "schema": schema,
                            "toolCallId": data.get("tool_call_id", ""),
                        },
                    )

            # --- confirm_required ---
            elif event_subtype == "confirm_required":
                confirm_call_id = data.get("tool_call_id") or f"confirm_{uuid.uuid4().hex[:12]}"
                approval_id = data.get("approval_id") or f"approval_{uuid.uuid4().hex[:12]}"
                action_desc = data.get("action", "执行操作")
                entities = data.get("entities", {})

                # If entities is empty, populate form fields based on intent
                if not entities and tracked_intent:
                    entities = get_confirmation_entities(tracked_intent)

                if entities.get("title"):
                    action_desc = entities["title"]

                yield _aisdk_event(
                    "tool-input-available",
                    toolCallId=confirm_call_id,
                    toolName="confirm_action",
                    input={"action": action_desc, "entities": entities},
                )
                yield _aisdk_event(
                    "tool-approval-request",
                    toolCallId=confirm_call_id,
                    approvalId=approval_id,
                )

            # --- done ---
            elif event_subtype == "done":
                # 关闭文本流
                if text_started:
                    yield _aisdk_event("text-end", id=text_id)
                    text_started = False

                # finish-step + finish
                yield _aisdk_event("finish-step")
                yield _aisdk_event("finish")
                yield "data: [DONE]\n\n"
                return

            # --- error ---
            elif event_subtype == "error":
                yield _aisdk_event("error", errorText=data.get("content", "Agent execution error"))
                yield "data: [DONE]\n\n"
                return

            # --- intent ---
            elif event_subtype == "intent":
                tracked_intent = data.get("intent_label", "")

            # --- mode (ignored) ---
            elif event_subtype == "mode":
                continue

    except Exception as e:
        logger.exception("AI SDK stream error")
        yield _aisdk_event("error", errorText=str(e))
        yield "data: [DONE]\n\n"
        return

    # 兜底：确保流正常终止
    if text_started:
        yield _aisdk_event("text-end", id=text_id)
    yield _aisdk_event("finish-step")
    yield _aisdk_event("finish")
    yield "data: [DONE]\n\n"


@router.post("/chat/aisdk")
async def chat_aisdk(
    request: Request,
    user: User = Depends(get_current_user),
):
    """AI SDK 协议聊天端点。

    接收 AI SDK UIMessage 请求，返回 AI SDK Data Stream Protocol 事件流。
    """
    body = await request.json()
    conversation_id = body.get("id")
    if not conversation_id:
        raise HTTPException(status_code=422, detail="缺少 conversation id")

    # 会话必须已创建且属于当前租户和用户；跨租户统一按未找到处理。
    conv_store = get_conversation_store()
    conversation = conv_store.get_conversation_for_user(
        conversation_id,
        user.tenant_id,
        user.user_id,
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="对话未找到")

    return StreamingResponse(
        _stream_aisdk_response(body, user.tenant_id, user.user_id, user.role),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "x-vercel-ai-ui-message-stream": "v1",
        },
    )
