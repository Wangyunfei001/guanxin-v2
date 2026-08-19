"""Agent 执行器模块。

负责处理用户消息，调用 LangGraph Agent，
并通过 SSE 流式返回结果。

支持两种模式（由 AGENT_MODE 环境变量控制）：
- state_graph（默认）：自定义 StateGraph，含意图分类 + 模式决策
- legacy：旧版 create_react_agent
"""

import json
import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.agent.graph import _create_llm, create_legacy_agent, create_state_graph_agent
from app.agent.prompts import DEFAULT_SYSTEM_PROMPT, build_system_prompt
from app.agent.tools import get_enabled_tools
from app.config import settings
from app.models.agent import ConversationMessage
from app.services.conversation_store import get_conversation_store

logger = logging.getLogger(__name__)


def _format_sse(data: dict) -> str:
    """格式化 SSE 消息。"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _mock_stream_response(
    user_message: str,
    system_prompt: str,
) -> AsyncGenerator[str, None]:
    """模拟流式响应（当 LLM 不可用时使用）。"""
    reply = (
        f"您好！我是观心 v2 的 AI 助手。\n\n"
        f"您发送的消息是：「{user_message}」\n\n"
        f"当前运行在演示模式（未配置 OpenAI API Key），无法调用大模型进行真正的推理。"
        f"请配置 OPENAI_API_KEY 环境变量以启用完整的 AI 对话能力。\n\n"
        f"您仍然可以：\n"
        f"- 上传文档到知识库\n"
        f"- 在 A2UI 预览页面查看组件\n"
        f"- 浏览技能市场\n"
        f"- 配置 MCP 服务器"
    )

    tokens = []
    for char in reply:
        tokens.append(char)

    chunk_size = 3
    for i in range(0, len(tokens), chunk_size):
        chunk = "".join(tokens[i : i + chunk_size])
        yield _format_sse({"type": "token", "content": chunk})
        await asyncio.sleep(0.02)

    yield _format_sse({"type": "done", "content": reply})


async def _build_message_history(
    user_message: str,
    conversation_id: str,
    tenant_id: str,
    system_prompt: str,
    include_system: bool = True,
) -> list:
    """构建消息列表（含历史消息）。

    Args:
        user_message: 当前用户消息
        conversation_id: 对话 ID
        tenant_id: 租户 ID
        system_prompt: 系统提示词
        include_system: 是否在消息列表中包含 system 消息

    Returns:
        消息 dict 列表
    """
    conv_store = get_conversation_store()
    conv_store.add_message(
        conversation_id,
        ConversationMessage(role="user", content=user_message),
    )

    conv = conv_store.get_conversation(conversation_id, tenant_id)
    history = conv.messages if conv else []

    messages = []
    if include_system:
        messages.append({"role": "system", "content": system_prompt})
    for msg in history[:-1]:  # 排除刚添加的用户消息
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})

    return messages


async def execute_agent(
    user_message: str,
    conversation_id: str,
    tenant_id: str,
    user_id: str,
    agent_id: str = "default",
    system_prompt: str = "",
    enabled_tools: Optional[List[str]] = None,
    model_name: str = "",
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    """执行 Agent 并流式返回结果。

    根据 settings.agent_mode 分发到 state_graph 或 legacy 模式。

    Yields:
        SSE 格式的流式消息
    """
    prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

    if settings.agent_mode == "legacy":
        async for msg in _execute_legacy(
            user_message, conversation_id, tenant_id, user_id,
            agent_id, prompt, enabled_tools, model_name, temperature,
        ):
            yield msg
    else:
        async for msg in _execute_state_graph(
            user_message, conversation_id, tenant_id, user_id,
            agent_id, prompt, enabled_tools, model_name, temperature,
        ):
            yield msg


async def _execute_legacy(
    user_message: str,
    conversation_id: str,
    tenant_id: str,
    user_id: str,
    agent_id: str,
    system_prompt: str,
    enabled_tools: Optional[List[str]],
    model_name: str,
    temperature: float,
) -> AsyncGenerator[str, None]:
    """Legacy 模式：使用 create_react_agent。"""
    messages = await _build_message_history(
        user_message, conversation_id, tenant_id, system_prompt, include_system=True
    )

    agent = create_legacy_agent(
        system_prompt=system_prompt,
        enabled_tools=enabled_tools,
        model_name=model_name,
        temperature=temperature,
    )

    if agent is None:
        full_response = ""
        async for sse_msg in _mock_stream_response(user_message, system_prompt):
            yield sse_msg
            if "done" in sse_msg:
                try:
                    data = json.loads(sse_msg.replace("data: ", "").strip())
                    full_response = data.get("content", "")
                except Exception:
                    pass

        conv_store = get_conversation_store()
        conv_store.add_message(
            conversation_id,
            ConversationMessage(role="assistant", content=full_response),
        )
        return

    full_response = ""
    try:
        async for event in agent.astream_events({"messages": messages}, version="v2"):
            async for sse_msg in _handle_stream_event(event):
                yield sse_msg
                if sse_msg.startswith("data: ") and '"type": "token"' in sse_msg:
                    try:
                        data = json.loads(sse_msg.replace("data: ", "").strip())
                        full_response += data.get("content", "")
                    except Exception:
                        pass
    except Exception as e:
        yield _format_sse({"type": "error", "content": f"Agent 执行出错: {str(e)}"})
        full_response = f"抱歉，处理您的请求时出错: {str(e)}"

    if not full_response:
        full_response = "（无输出）"

    conv_store = get_conversation_store()
    conv_store.add_message(
        conversation_id,
        ConversationMessage(role="assistant", content=full_response),
    )

    yield _format_sse({"type": "done", "content": full_response})


async def _execute_state_graph(
    user_message: str,
    conversation_id: str,
    tenant_id: str,
    user_id: str,
    agent_id: str,
    system_prompt: str,
    enabled_tools: Optional[List[str]],
    model_name: str,
    temperature: float,
) -> AsyncGenerator[str, None]:
    """StateGraph 模式：使用自定义 StateGraph，含意图分类和模式决策。"""
    # StateGraph 模式下不包含 system 消息（节点内部添加）
    messages = await _build_message_history(
        user_message, conversation_id, tenant_id, system_prompt, include_system=False
    )

    # 创建 LLM
    llm = _create_llm(model_name or settings.openai_model, temperature)
    if llm is None:
        full_response = ""
        async for sse_msg in _mock_stream_response(user_message, system_prompt):
            yield sse_msg
            if "done" in sse_msg:
                try:
                    data = json.loads(sse_msg.replace("data: ", "").strip())
                    full_response = data.get("content", "")
                except Exception:
                    pass

        conv_store = get_conversation_store()
        conv_store.add_message(
            conversation_id,
            ConversationMessage(role="assistant", content=full_response),
        )
        return

    # 获取工具
    tools = get_enabled_tools(enabled_tools or [])

    # 创建 StateGraph Agent
    agent = create_state_graph_agent(llm, tools, system_prompt)

    full_response = ""
    intent_sent = False
    mode_sent = False
    _confirm_stop = False

    try:
        async for event in agent.astream_events(
            {"messages": messages},
            version="v2",
        ):
            event_type = event.get("event", "")
            event_name = event.get("name", "")
            event_data = event.get("data", {})

            # 捕获 intent_parser 节点输出
            if (
                event_type == "on_chain_end"
                and event_name == "intent_parser"
                and not intent_sent
            ):
                output = event_data.get("output", {})
                if isinstance(output, dict):
                    intent_data = output.get("intent", {})
                    if isinstance(intent_data, dict) and intent_data.get("intent_label"):
                        yield _format_sse(
                            {
                                "type": "intent",
                                "intent_label": intent_data.get("intent_label", ""),
                                "confidence": intent_data.get("confidence", 0),
                                "method": intent_data.get("method", ""),
                            }
                        )
                        intent_sent = True

            # 捕获 mode_decision 节点输出
            elif (
                event_type == "on_chain_end"
                and event_name == "mode_decision"
                and not mode_sent
            ):
                output = event_data.get("output", {})
                if isinstance(output, dict):
                    mode = output.get("mode", "chat")
                    yield _format_sse({"type": "mode", "mode": mode})
                    mode_sent = True

                    # confirm 模式发送 confirm_required 事件，然后停止流
                    if mode == "confirm":
                        yield _format_sse(
                            {
                                "type": "confirm_required",
                                "action": "执行操作",
                                "entities": {},
                            }
                        )
                        _confirm_stop = True
                        break

            # LLM token 流
            elif event_type == "on_chat_model_stream":
                chunk = event_data.get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    full_response += chunk.content
                    yield _format_sse(
                        {"type": "token", "content": chunk.content}
                    )

            # 工具调用开始
            elif event_type == "on_tool_start":
                tool_input = event_data.get("input", {})
                if isinstance(tool_input, dict):
                    tool_input_str = json.dumps(tool_input, ensure_ascii=False)
                else:
                    tool_input_str = str(tool_input)
                yield _format_sse(
                    {
                        "type": "tool_call",
                        "tool_name": event_name,
                        "tool_input": tool_input_str,
                    }
                )

            # 工具调用结束
            elif event_type == "on_tool_end":
                output = event_data.get("output", "")
                output_str = str(output) if output else ""

                yield _format_sse(
                    {
                        "type": "tool_result",
                        "tool_name": event_name,
                        "tool_output": output_str,
                    }
                )

                # 自动生成 A2UI schema
                try:
                    from app.a2ui.renderer import generate_for_tool_result

                    tool_input = event_data.get("input", {})
                    tool_input_dict = {}
                    if isinstance(tool_input, dict):
                        tool_input_dict = tool_input
                    elif isinstance(tool_input, str):
                        try:
                            tool_input_dict = json.loads(tool_input)
                        except Exception:
                            tool_input_dict = {"input": tool_input}

                    a2ui_schema = generate_for_tool_result(
                        tool_name=event_name,
                        tool_input=tool_input_dict,
                        tool_output=output_str,
                    )
                    if a2ui_schema:
                        yield _format_sse({"type": "a2ui", "schema": a2ui_schema})
                except Exception:
                    pass

    except Exception as e:
        logger.error("StateGraph execution error: %s", e)
        yield _format_sse({"type": "error", "content": f"Agent 执行出错: {str(e)}"})
        full_response = f"抱歉，处理您的请求时出错: {str(e)}"

    # confirm 模式：流已停止，等待用户确认后重新发起请求
    if _confirm_stop:
        conv_store = get_conversation_store()
        conv_store.add_message(
            conversation_id,
            ConversationMessage(role="assistant", content="等待用户确认操作..."),
        )
        yield _format_sse({"type": "done", "content": "等待用户确认操作..."})
        return

    if not full_response:
        full_response = "（无输出）"

    # 保存助手消息
    conv_store = get_conversation_store()
    conv_store.add_message(
        conversation_id,
        ConversationMessage(role="assistant", content=full_response),
    )

    yield _format_sse({"type": "done", "content": full_response})


async def _handle_stream_event(event: dict) -> AsyncGenerator[str, None]:
    """处理 LangGraph astream_events 事件，生成 SSE 消息（legacy 模式用）。

    Args:
        event: astream_events 事件 dict

    Yields:
        SSE 格式消息
    """
    event_type = event.get("event", "")
    event_name = event.get("name", "")
    event_data = event.get("data", {})

    # LLM token 流
    if event_type == "on_chat_model_stream":
        chunk = event_data.get("chunk")
        if chunk and hasattr(chunk, "content") and chunk.content:
            yield _format_sse({"type": "token", "content": chunk.content})

    # 工具调用开始
    elif event_type == "on_tool_start":
        tool_input = event_data.get("input", {})
        if isinstance(tool_input, dict):
            tool_input_str = json.dumps(tool_input, ensure_ascii=False)
        else:
            tool_input_str = str(tool_input)
        yield _format_sse(
            {
                "type": "tool_call",
                "tool_name": event_name,
                "tool_input": tool_input_str,
            }
        )

    # 工具调用结束
    elif event_type == "on_tool_end":
        output = event_data.get("output", "")
        output_str = str(output) if output else ""

        yield _format_sse(
            {
                "type": "tool_result",
                "tool_name": event_name,
                "tool_output": output_str,
            }
        )

        # 自动生成 A2UI schema
        try:
            from app.a2ui.renderer import generate_for_tool_result

            tool_input_dict = {}
            if isinstance(tool_input, dict):
                tool_input_dict = tool_input
            elif isinstance(tool_input, str):
                try:
                    tool_input_dict = json.loads(tool_input)
                except Exception:
                    tool_input_dict = {"input": tool_input}

            a2ui_schema = generate_for_tool_result(
                tool_name=event_name,
                tool_input=tool_input_dict,
                tool_output=output_str,
            )
            if a2ui_schema:
                yield _format_sse({"type": "a2ui", "schema": a2ui_schema})
        except Exception:
            pass
