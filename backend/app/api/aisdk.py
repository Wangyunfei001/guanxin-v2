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

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.agent.executor import execute_agent
from app.core.tenant import get_tenant_id

logger = logging.getLogger(__name__)

# Intent → confirm form fields mapping
_CONFIRM_FORM_FIELDS: dict = {
    "single_create": {
        "title": "创建新用户",
        "fields": [
            {"name": "username", "label": "用户名", "type": "text", "required": True, "placeholder": "请输入用户名"},
            {"name": "email", "label": "邮箱", "type": "email", "required": True, "placeholder": "请输入邮箱地址"},
            {"name": "role", "label": "角色", "type": "select", "required": False, "options": ["admin", "user", "viewer"], "default": "user"},
        ],
    },
    "single_update": {
        "title": "更新用户信息",
        "fields": [
            {"name": "user_id", "label": "用户ID", "type": "text", "required": True, "placeholder": "请输入用户ID"},
            {"name": "username", "label": "新用户名", "type": "text", "required": False, "placeholder": "留空则不修改"},
            {"name": "email", "label": "新邮箱", "type": "email", "required": False, "placeholder": "留空则不修改"},
            {"name": "role", "label": "新角色", "type": "select", "required": False, "options": ["admin", "user", "viewer"]},
        ],
    },
    "single_delete": {
        "title": "删除用户",
        "fields": [
            {"name": "user_id", "label": "用户ID", "type": "text", "required": True, "placeholder": "请输入要删除的用户ID"},
        ],
        "danger": True,
    },
    "batch_operation": {
        "title": "导出数据",
        "fields": [
            {"name": "data_type", "label": "数据类型", "type": "select", "required": True, "options": ["users", "logs", "reports"]},
            {"name": "format", "label": "导出格式", "type": "select", "required": False, "options": ["csv", "json", "xlsx"], "default": "csv"},
            {"name": "date_range", "label": "日期范围", "type": "text", "required": False, "placeholder": "如: 2024-01-01~2024-12-31"},
        ],
    },
}


def _get_confirm_fields(intent_label: str) -> dict:
    """Get confirm form field definitions for an intent."""
    return _CONFIRM_FORM_FIELDS.get(intent_label, {})


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
) -> AsyncGenerator[str, None]:
    """将 RunAgentInput 转换为 AI SDK Data Stream Protocol 事件流。

    Args:
        input_body: AG-UI RunAgentInput JSON（兼容格式）
        tenant_id: 租户 ID
        user_id: 用户 ID
    """
    messages = input_body.get("messages", [])

    # 提取最后一条用户消息
    # AI SDK 格式: { role, parts: [{type:"text", text:"..."}] }
    # AG-UI 格式: { role, content: "..." }
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

    # 如果是确认/取消协议消息，从历史中找到原始请求注入到上下文中
    if user_message.startswith("✅ 确认操作：") or user_message.startswith("取消操作："):
        for msg in messages:
            if msg.get("role") == "user":
                text = _extract_user_text(msg)
                if text and not text.startswith("✅") and not text.startswith("取消"):
                    user_message = f"{user_message}\n\n原始请求：{text}"
                    break

    # 生成唯一 ID
    message_id = f"msg_{uuid.uuid4().hex[:12]}"
    text_id = f"text_{uuid.uuid4().hex[:12]}"

    # 状态标志
    text_started = False
    message_started = False
    tracked_intent: str = ""
    # 追踪 tool_call → AI-SDK toolCallId 的映射（用于 tool_result 时回填）
    pending_tool_calls: Dict[str, str] = {}  # tool_name → toolCallId

    conversation_id = input_body.get("id", str(uuid.uuid4()))

    # 从 messages 中提取第一条用户消息内容，生成稳定的 conversation_id
    # 这样同一对话的多次请求共享同一个 conversation_id，后端可以从 DB 加载历史
    first_user_text = ""
    for msg in messages:
        if msg.get("role") == "user":
            first_user_text = _extract_user_text(msg)
            break
    if first_user_text:
        import hashlib
        conversation_id = hashlib.md5(
            f"{tenant_id}:{first_user_text}".encode()
        ).hexdigest()[:16]

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
                tool_call_id = f"call_{uuid.uuid4().hex[:12]}"
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
                tool_call_id = pending_tool_calls.pop(tool_name, f"call_{uuid.uuid4().hex[:12]}")

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
                    yield _aisdk_event("data-a2ui", data=schema)

            # --- confirm_required ---
            elif event_subtype == "confirm_required":
                confirm_call_id = f"confirm_{uuid.uuid4().hex[:12]}"
                approval_id = f"approval_{uuid.uuid4().hex[:12]}"
                action_desc = data.get("action", "执行操作")
                entities = data.get("entities", {})

                # If entities is empty, populate form fields based on intent
                if not entities and tracked_intent:
                    entities = _get_confirm_fields(tracked_intent)

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
async def chat_aisdk(request: Request):
    """AI SDK 协议聊天端点。

    接收 RunAgentInput JSON（与 AG-UI 兼容），返回 AI SDK Data Stream Protocol 事件流。
    """
    body = await request.json()

    # 提取用户信息
    tenant_id = get_tenant_id() or "default"
    user_id = request.headers.get("X-User-Id", "anonymous")

    return StreamingResponse(
        _stream_aisdk_response(body, tenant_id, user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "x-vercel-ai-ui-message-stream": "v1",
        },
    )