"""ChatResponder 节点 — 聊天回复。

处理 mode=chat 的闲聊/问候场景，直接 LLM 回复，不加载任何工具。
"""

import logging
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage

from app.agent.state import AgentState

logger = logging.getLogger(__name__)


def create_chat_responder_node(llm: Any, system_prompt: str):
    """创建 ChatResponder 节点函数。

    Args:
        llm: LLM 实例（ChatOpenAI 等）
        system_prompt: 系统提示词

    Returns:
        异步节点函数，输入 AgentState，输出 state 更新 dict。
        不传 tools，LLM 仅做纯文本回复。
    """

    async def chat_responder_node(state: AgentState) -> dict:
        """聊天回复节点。

        1. 使用 system_prompt + messages 列表调用 LLM（不带 tool）
        2. LLM 输出文本
        3. 返回 {"final_response": ..., "messages": [AIMessage(...)]}
        """
        messages = list(state.get("messages", []))

        # 在消息列表前插入 system prompt
        llm_messages = [SystemMessage(content=system_prompt)] + messages

        try:
            response = await llm.ainvoke(llm_messages)
            content = response.content if hasattr(response, "content") else str(response)

            logger.debug("ChatResponder generated response: %s", content[:100])

            return {
                "final_response": content,
                "messages": [AIMessage(content=content)],
            }
        except Exception as e:
            logger.error("ChatResponder LLM call failed: %s", e)
            error_msg = f"抱歉，处理您的请求时出错: {str(e)}"
            return {
                "final_response": error_msg,
                "messages": [AIMessage(content=error_msg)],
            }

    return chat_responder_node
