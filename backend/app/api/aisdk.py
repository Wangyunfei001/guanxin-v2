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

from app.agent.executor import execute_agent
from app.agent.supervisor import decide_route
from app.agent.tool_catalog import build_tool_catalog
from app.core.deps import get_current_user
from app.models.tenant import User
from app.models.agent import ConversationMessage
from app.services.conversation_store import get_conversation_store
from app.workflows.engine import resume_workflow, start_workflow
from app.workflows.planner import WorkflowPlannerError, detect_workflow_intent
from app.workflows.catalog import catalog_by_name
from app.workflows.presentation import pending_workflow_part, workflow_public_data
from app.models.agent import get_agent_config_store
from app.services.workflow_store import (
    WorkflowConflictError,
    get_workflow_store,
)
from app.research.engine import public_research_snapshot, run_research

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


async def _emit_workflow_state(
    run: dict[str, Any],
    *,
    message_id: str,
    responded_tool_call_id: str = "",
) -> AsyncGenerator[str, None]:
    """Reconcile a workflow snapshot into its stable assistant message."""
    yield _aisdk_event("start", messageId=message_id)
    data = workflow_public_data(run)
    yield _aisdk_event("data-workflow", id=run["run_id"], data=data)
    if responded_tool_call_id:
        yield _aisdk_event(
            "tool-output-available",
            toolCallId=responded_tool_call_id,
            output={"run_id": run["run_id"], "status": run["status"]},
        )
    pending_part = pending_workflow_part(run)
    if pending_part:
        yield _aisdk_event(
            "tool-input-available",
            toolCallId=pending_part["toolCallId"],
            toolName="workflow_control",
            input=pending_part["input"],
        )
        yield _aisdk_event(
            "tool-approval-request",
            toolCallId=pending_part["toolCallId"],
            approvalId=pending_part["approval"]["id"],
        )
    yield _aisdk_event("finish-step")
    yield _aisdk_event("finish")
    yield "data: [DONE]\n\n"


async def _stream_workflow_start(
    *,
    user_message: str,
    intent: str,
    conversation_id: str,
    tenant_id: str,
    user_id: str,
    user_role: str,
    agent_id: str,
) -> AsyncGenerator[str, None]:
    conv_store = get_conversation_store()
    conv_store.add_message(
        conversation_id,
        ConversationMessage(role="user", content=user_message),
    )
    try:
        run = await start_workflow(
            user_message=user_message,
            intent=intent,
            tenant_id=tenant_id,
            user_id=user_id,
            user_role=user_role,
            conversation_id=conversation_id,
            agent_id=agent_id,
        )
    except (WorkflowPlannerError, WorkflowConflictError) as exc:
        message = f"无法创建工作流：{exc}"
        conv_store.add_message(
            conversation_id,
            ConversationMessage(
                role="assistant",
                content=message,
                parts=[{"type": "text", "text": message}],
            ),
        )
        yield _aisdk_event("error", errorText=str(exc))
        yield "data: [DONE]\n\n"
        return
    data = workflow_public_data(run)
    pending_part = pending_workflow_part(run)
    message_id = conv_store.upsert_workflow_message(
        conversation_id, run["run_id"], data, pending_part
    )
    if message_id is None:
        yield _aisdk_event("error", errorText="工作流消息持久化失败")
        yield "data: [DONE]\n\n"
        return
    async for event in _emit_workflow_state(run, message_id=message_id):
        yield event


async def _stream_workflow_resume(
    approval_response: dict[str, Any],
    *,
    tenant_id: str,
    user_id: str,
    user_role: str,
) -> AsyncGenerator[str, None]:
    values = _approval_params(approval_response.get("reason", ""))
    try:
        run = await resume_workflow(
            interrupt_id=approval_response["approval_id"],
            accepted=approval_response["approved"],
            values=values,
            tenant_id=tenant_id,
            user_id=user_id,
            user_role=user_role,
        )
    except (LookupError, PermissionError) as exc:
        yield _aisdk_event("error", errorText=str(exc))
        yield "data: [DONE]\n\n"
        return
    conv_store = get_conversation_store()
    data = workflow_public_data(run)
    pending_part = pending_workflow_part(run)
    message_id = conv_store.upsert_workflow_message(
        run["conversation_id"], run["run_id"], data, pending_part
    )
    if message_id is None:
        yield _aisdk_event("error", errorText="工作流消息持久化失败")
        yield "data: [DONE]\n\n"
        return
    async for event in _emit_workflow_state(
        run,
        message_id=message_id,
        responded_tool_call_id=approval_response.get("tool_call_id", ""),
    ):
        yield event


async def _stream_research(
    *,
    user_message: str,
    conversation_id: str,
    tenant_id: str,
    user_id: str,
    mode: str,
    catalog: list,
) -> AsyncGenerator[str, None]:
    """Stream a persistent Research run as a standard AI SDK data part."""
    conv_store = get_conversation_store()
    conv_store.add_message(
        conversation_id,
        ConversationMessage(role="user", content=user_message),
    )
    message_id = f"msg_{uuid.uuid4().hex[:12]}"
    text_id = f"text_{uuid.uuid4().hex[:12]}"
    yield _aisdk_event("start", messageId=message_id)
    final_snapshot: dict[str, Any] = {}
    async for snapshot in run_research(
        tenant_id=tenant_id,
        user_id=user_id,
        conversation_id=conversation_id,
        goal=user_message,
        mode=mode,
        catalog=catalog,
    ):
        final_snapshot = snapshot
        yield _aisdk_event("data-research", id=snapshot["run_id"], data=snapshot)

    report = str(final_snapshot.get("report") or "")
    if not report and final_snapshot.get("status") == "cancelled":
        report = "研究已取消。"
    if not report and final_snapshot.get("error"):
        report = f"研究未完成：{final_snapshot['error']}"
    parts: list[dict[str, Any]] = [
        {
            "type": "data-research",
            "id": final_snapshot.get("run_id", ""),
            "data": final_snapshot,
        }
    ]
    if report:
        parts.append({"type": "text", "text": report})
        yield _aisdk_event("text-start", id=text_id)
        yield _aisdk_event("text-delta", id=text_id, delta=report)
        yield _aisdk_event("text-end", id=text_id)
    conv_store.add_message(
        conversation_id,
        ConversationMessage(role="assistant", content=report, parts=parts),
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
        workflow_interrupt = get_workflow_store().get_interrupt(
            approval_response["approval_id"]
        )
        if workflow_interrupt is not None:
            async for event in _stream_workflow_resume(
                approval_response,
                tenant_id=tenant_id,
                user_id=user_id,
                user_role=user_role,
            ):
                yield event
            return
        yield _aisdk_event(
            "error",
            errorText="旧审批链路已停用；历史记录仅支持查看",
        )
        yield "data: [DONE]\n\n"
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

    research_mode = str(input_body.get("research_mode", "auto"))
    config = get_agent_config_store().get_or_create_default(tenant_id)
    catalog = await build_tool_catalog(
        config,
        tenant_id=tenant_id,
        user_id=user_id,
        user_role=user_role,
        conversation_id=input_body["id"],
    )
    decision = await decide_route(
        user_message,
        config,
        catalog,
        research_mode=research_mode,
    )

    if decision.route == "write_workflow":
        workflow_intent = detect_workflow_intent(user_message) or "multi_step_flow"
        async for event in _stream_workflow_start(
            user_message=user_message,
            intent=workflow_intent,
            conversation_id=input_body["id"],
            tenant_id=tenant_id,
            user_id=user_id,
            user_role=user_role,
            agent_id="default",
        ):
            yield event
        return

    if decision.route == "research":
        mode = "deep" if decision.research_mode == "deep" else "quick"
        async for event in _stream_research(
            user_message=user_message,
            conversation_id=input_body["id"],
            tenant_id=tenant_id,
            user_id=user_id,
            mode=mode,
            catalog=catalog,
        ):
            yield event
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
            route_decision=decision,
            catalog=catalog,
            research_mode=research_mode,
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
                if not message_started:
                    yield _aisdk_event("start", messageId=message_id)
                    message_started = True
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
                yield _aisdk_event(
                    "error",
                    errorText="旧确认执行分支已停用，请通过持久化工作流重试",
                )
                yield "data: [DONE]\n\n"
                return

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
    if body.get("research_mode", "auto") not in {"auto", "quick", "deep"}:
        raise HTTPException(status_code=422, detail="research_mode 必须为 auto、quick 或 deep")

    # 会话必须已创建且属于当前租户和用户；跨租户统一按未找到处理。
    conv_store = get_conversation_store()
    conversation = conv_store.get_conversation_for_user(
        conversation_id,
        user.tenant_id,
        user.user_id,
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="对话未找到")

    approval_response = _find_approval_response(body.get("messages", []))
    if approval_response and approval_response.get("approved"):
        workflow_interrupt = get_workflow_store().get_interrupt(
            approval_response["approval_id"]
        )
        if workflow_interrupt is not None:
            workflow_run = get_workflow_store().get_run(
                workflow_interrupt["run_id"], user.tenant_id, user.user_id
            )
            if workflow_run is None:
                raise HTTPException(status_code=404, detail="工作流未找到")
            step = next(
                (
                    item for item in workflow_run["steps"]
                    if item["step_id"] == workflow_interrupt["step_id"]
                ),
                None,
            )
            config = get_agent_config_store().get_config(
                user.tenant_id, workflow_run["agent_id"]
            )
            allowed = catalog_by_name(config, user.role) if config else {}
            if step is None or step["tool_name"] not in allowed:
                raise HTTPException(status_code=403, detail="工具已禁用或当前用户无权执行")
    active_run = get_workflow_store().get_active_for_conversation(
        conversation_id, user.tenant_id, user.user_id
    )
    if active_run and not approval_response:
        raise HTTPException(status_code=409, detail="请先处理或取消当前工作流")

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
