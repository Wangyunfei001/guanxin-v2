"""ReActToolExecutor 节点 — 工具执行。

处理 mode=direct 或 mode=confirm 场景，
复用 create_react_agent 子图能力。
"""

import logging
from typing import Any

from langchain_core.messages import AIMessage

from app.agent.prompts import DEFAULT_SYSTEM_PROMPT, CONFIRM_MODE_PROMPT_SUFFIX, build_system_prompt
from app.agent.state import AgentState, ModeEnum

logger = logging.getLogger(__name__)

# 确认执行模式下注入的 prompt 后缀
CONFIRMED_EXECUTION_PROMPT_SUFFIX = """

## 重要：用户已确认执行

用户刚才发送了一条"✅ 确认操作："开头的确认消息，表示同意执行之前讨论的操作。

你现在的工作是：
1. **回顾对话历史**，找到用户最初的需求（确认消息之前的 user 消息）
2. **立即调用相应的工具**来满足那个原始需求
3. **如果缺少必填参数，使用合理的默认值**（如 username="demo_user", email="demo@test.com"）
4. **不要闲聊、不要追问用户要更多信息**，直接执行工具调用
5. 工具执行完成后，**简要汇报结果**即可

注意：用户当前的确认消息只是协议消息，不要把它当作新的用户需求来回复。
"""


def _get_last_human_message_text(state: AgentState) -> str:
    """从 state["messages"] 中获取最后一条 HumanMessage 的纯文本内容。"""
    messages = state.get("messages", [])
    for msg in reversed(messages):
        msg_type = getattr(msg, "type", "")
        if msg_type == "human" or msg.__class__.__name__ == "HumanMessage":
            content = getattr(msg, "content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        return part.get("text", "")
                    if isinstance(part, str):
                        return part
            return ""
    return ""


def create_react_executor_node(
    llm: Any,
    tools: list,
    system_prompt: str = "",
):
    """创建 ReActToolExecutor 节点函数。

    Args:
        llm: LLM 实例（ChatOpenAI 等）
        tools: LangChain Tool 列表
        system_prompt: 基础系统提示词

    Returns:
        异步节点函数，根据 state["mode"] 构建 prompt 并执行 ReAct 子 Agent。
    """

    async def react_executor_node(state: AgentState) -> dict:
        """ReAct 工具执行节点。

        1. 根据 mode 动态构建 system_prompt:
           - mode=direct: 标准 ReAct prompt
           - mode=confirm: 标准 prompt + 确认指令
        2. 调用 create_react_agent 子图
        3. 返回 {"final_response": result, "messages": [AIMessage(...)]}
        """
        mode = state.get("mode", ModeEnum.DIRECT.value)
        messages = list(state.get("messages", []))

        # 检查是否为确认/取消消息
        last_human_text = _get_last_human_message_text(state)
        is_confirm = last_human_text.startswith("✅ 确认操作：")
        is_cancel = last_human_text.startswith("取消操作：")

        if is_cancel:
            cancel_msg = "已取消操作。有什么我可以帮您的吗？"
            return {
                "final_response": cancel_msg,
                "messages": [AIMessage(content=cancel_msg)],
            }

        # 构建系统提示词
        base_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        full_prompt = build_system_prompt(
            base_prompt=base_prompt,
            enabled_tools=[t.name for t in tools],
        )

        if is_confirm:
            full_prompt += CONFIRMED_EXECUTION_PROMPT_SUFFIX
        elif mode == ModeEnum.CONFIRM.value:
            full_prompt += CONFIRM_MODE_PROMPT_SUFFIX

        # 创建并执行 ReAct 子 Agent
        try:
            from langgraph.prebuilt import create_react_agent

            react_agent = create_react_agent(
                model=llm,
                tools=tools,
                prompt=full_prompt,
            )

            # 调用子 Agent
            result = await react_agent.ainvoke({"messages": messages})

            # 提取最后一条 AI 消息作为最终回复
            result_messages = result.get("messages", [])
            final_content = ""
            for msg in reversed(result_messages):
                if hasattr(msg, "content") and msg.__class__.__name__ == "AIMessage":
                    final_content = msg.content
                    break

            if not final_content:
                final_content = "（无输出）"

            logger.debug(
                "ReActExecutor (mode=%s) generated response: %s",
                mode,
                final_content[:100],
            )

            return {
                "final_response": final_content,
                "messages": [AIMessage(content=final_content)],
            }

        except ImportError:
            logger.error("langgraph.prebuilt.create_react_agent not available")
            error_msg = "Agent 执行工具不可用（缺少 langgraph）"
            return {
                "final_response": error_msg,
                "messages": [AIMessage(content=error_msg)],
            }
        except Exception as e:
            logger.error("ReActExecutor failed: %s", e)
            error_msg = f"抱歉，处理您的请求时出错: {str(e)}"
            return {
                "final_response": error_msg,
                "messages": [AIMessage(content=error_msg)],
            }

    return react_executor_node
