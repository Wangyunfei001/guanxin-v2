"""Agent 图模块。

支持两种模式：
- state_graph（默认）：自定义 StateGraph，含意图分类 + 模式决策 + 条件路由
- legacy：旧版 create_react_agent（AGENT_MODE=legacy 切回）
"""

import logging
from typing import Any, List, Optional

from app.agent.prompts import DEFAULT_SYSTEM_PROMPT, build_system_prompt
from app.agent.tools import get_enabled_tools, get_tools, get_tools_description
from app.config import settings

logger = logging.getLogger(__name__)


def create_state_graph_agent(
    llm: Any,
    tools: List,
    system_prompt: str = "",
):
    """构建自定义 StateGraph Agent。

    节点流程：
        START → intent_parser → mode_decision
            ├─ mode=chat → chat_responder → END
            └─ mode=direct/confirm → react_executor → END

    Args:
        llm: LLM 实例（ChatOpenAI 等）
        tools: LangChain Tool 列表
        system_prompt: 系统提示词

    Returns:
        编译后的 StateGraph
    """
    from langgraph.graph import StateGraph, START, END

    from app.agent.nodes import (
        create_chat_responder_node,
        create_intent_parser_node,
        create_mode_decision_node,
        create_react_executor_node,
    )
    from app.agent.nodes.mode_decision import route_after_mode_decision
    from app.agent.state import AgentState

    prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

    workflow = StateGraph(AgentState)

    # 1. 注册节点
    workflow.add_node("intent_parser", create_intent_parser_node(llm))
    workflow.add_node("mode_decision", create_mode_decision_node())
    workflow.add_node("chat_responder", create_chat_responder_node(llm, prompt))
    workflow.add_node("react_executor", create_react_executor_node(llm, tools, prompt))

    # 2. 注册边
    workflow.add_edge(START, "intent_parser")
    workflow.add_edge("intent_parser", "mode_decision")

    # 3. 条件路由
    workflow.add_conditional_edges(
        "mode_decision",
        route_after_mode_decision,
        {
            "chat_responder": "chat_responder",
            "react_executor": "react_executor",
        },
    )

    workflow.add_edge("chat_responder", END)
    workflow.add_edge("react_executor", END)

    return workflow.compile()


def create_legacy_agent(
    system_prompt: str = "",
    enabled_tools: Optional[List[str]] = None,
    model_name: str = "",
    temperature: float = 0.7,
    user_role: str = "user",
    max_tokens: int = 4096,
):
    """创建旧版 create_react_agent（Legacy 兼容模式）。

    Args:
        system_prompt: 系统提示词
        enabled_tools: 启用的工具名称列表
        model_name: LLM 模型名称
        temperature: 温度参数

    Returns:
        LangGraph 编译后的 Agent，LLM 不可用时返回 None
    """
    tools = get_enabled_tools(enabled_tools or [], user_role=user_role)

    prompt = build_system_prompt(
        base_prompt=system_prompt or DEFAULT_SYSTEM_PROMPT,
        enabled_tools=[t.name for t in tools],
    )

    llm = _create_llm(model_name or settings.openai_model, temperature, max_tokens)

    if llm is None:
        return None

    try:
        from langgraph.prebuilt import create_react_agent

        agent = create_react_agent(
            model=llm,
            tools=tools,
            prompt=prompt,
        )
        return agent
    except Exception:
        return None


# 保留旧函数名作为别名，兼容已有调用
create_agent_graph = create_legacy_agent


def create_agent(
    system_prompt: str = "",
    enabled_tools: Optional[List[str]] = None,
    model_name: str = "",
    temperature: float = 0.7,
    user_role: str = "user",
    max_tokens: int = 4096,
):
    """根据 AGENT_MODE 创建 Agent。

    Args:
        system_prompt: 系统提示词
        enabled_tools: 启用工具列表
        model_name: 模型名称
        temperature: 温度参数

    Returns:
        编译后的 Agent（StateGraph 或 create_react_agent），
        LLM 不可用时返回 None
    """
    if settings.agent_mode == "legacy":
        return create_legacy_agent(
            system_prompt=system_prompt,
            enabled_tools=enabled_tools,
            model_name=model_name,
            temperature=temperature,
            user_role=user_role,
            max_tokens=max_tokens,
        )

    # state_graph 模式
    llm = _create_llm(model_name or settings.openai_model, temperature, max_tokens)
    if llm is None:
        return None

    tools = get_enabled_tools(enabled_tools or [], user_role=user_role)
    return create_state_graph_agent(llm, tools, system_prompt)


def _create_llm(model_name: str, temperature: float, max_tokens: int = 4096):
    """创建 LLM 实例。

    Args:
        model_name: 模型名称
        temperature: 温度

    Returns:
        ChatOpenAI 实例，失败返回 None
    """
    api_key = settings.openai_api_key
    if not api_key or api_key == "sk-your-api-key-here":
        return None

    try:
        from langchain_openai import ChatOpenAI

        model_kwargs: dict[str, Any] = {}
        # DeepSeek V4 enables thinking by default. This app deliberately keeps
        # Chat Completions non-thinking so forced tool choice and LangChain's
        # structured-output calls remain compatible, and no raw CoT needs to be
        # replayed across tool turns. Research uses the Responses API separately.
        if model_name.startswith("deepseek-v4-"):
            model_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=api_key,
            base_url=settings.openai_api_base,
            streaming=True,
            max_tokens=max_tokens,
            **model_kwargs,
        )
    except Exception:
        return None


def get_tools_desc() -> str:
    """获取工具描述文本。"""
    return get_tools_description(get_tools())
