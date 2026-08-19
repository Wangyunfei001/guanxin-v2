"""ModeDecision 节点 — 模式决策。

根据 IntentParser 输出的意图标签，决定交互模式（chat/direct/confirm）。
"""

import logging

from app.agent.state import AgentState, ModeEnum

logger = logging.getLogger(__name__)

# 意图 → 模式映射表
INTENT_TO_MODE: dict[str, str] = {
    "chat":              ModeEnum.CHAT.value,      # 闲聊，无工具
    "knowledge_query":   ModeEnum.DIRECT.value,    # 静默执行 kb_retrieval + 汇总
    "data_query":        ModeEnum.DIRECT.value,    # 静默执行查询工具
    "single_create":     ModeEnum.CONFIRM.value,   # 需用户确认
    "single_update":     ModeEnum.CONFIRM.value,   # 需用户确认
    "single_delete":     ModeEnum.CONFIRM.value,   # 需用户确认
    "batch_operation":   ModeEnum.CONFIRM.value,   # 批量操作需确认
    "multi_step_flow":   ModeEnum.DIRECT.value,    # P0 简化为 ReAct 子 Agent
    "system_diagnosis":  ModeEnum.DIRECT.value,    # 诊断直接执行
    "ticket_submit":     ModeEnum.CONFIRM.value,   # 提交工单需确认
}


def create_mode_decision_node():
    """创建 ModeDecision 节点函数。

    Returns:
        异步节点函数，读取 state["intent"]["intent_label"]，
        查表获取 mode，返回 state 更新 dict。
    """

    async def mode_decision_node(state: AgentState) -> dict:
        """模式决策节点。

        1. 检查最后一条用户消息是否为确认/取消消息，
           是则直接返回 direct/chat，不再依赖意图分类。
        2. 否则从 state["intent"]["intent_label"] 读取意图
        3. 查表 INTENT_TO_MODE 获取 mode
        4. 返回 {"mode": "<mode_value>"}
        """
        # 检查是否为确认/取消消息（前端 confirm_form 提交的消息）
        text = _get_last_human_message_text(state)
        if text.startswith("✅ 确认操作："):
            logger.debug("ModeDecision: confirmation detected, mode=direct")
            return {"mode": ModeEnum.DIRECT.value}
        if text.startswith("取消操作："):
            logger.debug("ModeDecision: cancellation detected, mode=chat")
            return {"mode": ModeEnum.CHAT.value}

        intent = state.get("intent", {})
        intent_label = intent.get("intent_label", "chat")

        mode = INTENT_TO_MODE.get(intent_label, ModeEnum.CHAT.value)

        logger.debug(
            "ModeDecision: intent=%s -> mode=%s",
            intent_label,
            mode,
        )

        return {"mode": mode}

    return mode_decision_node


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


def route_after_mode_decision(state: AgentState) -> str:
    """条件路由函数：根据 mode 决定下一个节点。

    Args:
        state: 当前 AgentState

    Returns:
        节点名称："chat_responder" 或 "react_executor"
    """
    mode = state.get("mode", ModeEnum.CHAT.value)
    if mode == ModeEnum.CHAT.value:
        return "chat_responder"
    else:
        return "react_executor"
