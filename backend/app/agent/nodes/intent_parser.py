"""IntentParser 节点 — 意图分类。

正则规则表（按优先级从高到低顺序匹配）+ LLM fallback（单 token 分类）。
"""

import re
import logging
from typing import Any

from app.agent.state import AgentState, IntentEnum

logger = logging.getLogger(__name__)

# 正则规则表：按优先级从高到低顺序匹配，第一条命中即返回
# 格式: (regex, intent_label, entities_extractor_dict_or_None)
INTENT_REGEX_RULES: list[tuple[str, str, dict | None]] = [
    # --- 第 -1 层：确认/取消协议消息（最高优先级，防止 LLM 误分类）---
    (
        r"^✅ 确认操作：",
        IntentEnum.CHAT.value,  # 实际路由由 mode_decision 接管
        None,
    ),
    (
        r"^取消操作：",
        IntentEnum.CHAT.value,  # 实际路由由 mode_decision 接管
        None,
    ),

    # --- 第 0 层：闲聊、打招呼（最高优先级）---
    (
        r"^(你好|hi|hello|嗨|早上好|晚上好|下午好|好久不见|在吗|嘿|hello there)",
        IntentEnum.CHAT.value,
        None,
    ),

    # --- 第 1 层：知识类问句 ---
    (
        r"(什么是|什么叫|啥是|介绍.*一下|.*是什么概念|.*是什么意思|.*的定义)",
        IntentEnum.KNOWLEDGE_QUERY.value,
        None,
    ),
    (
        r"(知识库|知识.*文档|上传.*文档).*(怎么|如何|怎样)",
        IntentEnum.KNOWLEDGE_QUERY.value,
        None,
    ),

    # --- 第 2 层：数据查询 ---
    (
        r"(查询|查看|列出|显示|有哪些|搜索|检索|找一下).*(租户|用户|账号|权限|角色|日志|任务|skill|技能)",
        IntentEnum.DATA_QUERY.value,
        None,
    ),
    (
        r"^(查|搜).*(租户|用户|列表|skill|技能)",
        IntentEnum.DATA_QUERY.value,
        None,
    ),

    # --- 第 3 层：单条 CRUD ---
    (
        r"(新增|创建|添加|新建|开通|注册).*(租户|用户|账号|项目|空间)",
        IntentEnum.SINGLE_CREATE.value,
        None,
    ),
    (
        r"(修改|更新|编辑|更改|重命名|调整|配置).*(租户|用户|账号|项目|设置|名称)",
        IntentEnum.SINGLE_UPDATE.value,
        None,
    ),
    (
        r"(删除|移除|注销|停用|禁用|清理).*(租户|用户|账号|项目)",
        IntentEnum.SINGLE_DELETE.value,
        None,
    ),

    # --- 第 4 层：批量操作 ---
    (
        r"(批量|导入|导出|迁移|同步|全部.*升级|全部.*更新)",
        IntentEnum.BATCH_OPERATION.value,
        None,
    ),

    # --- 第 5 层：系统诊断 ---
    (
        r"(系统.*慢|为什么.*慢|排查|诊断|性能|日志.*报错|看.*日志|检查.*状态)",
        IntentEnum.SYSTEM_DIAGNOSIS.value,
        None,
    ),

    # --- 第 6 层：工单 ---
    (
        r"(工单|报错|故障|bug|问题反馈|提个.*issue|提交.*问题)",
        IntentEnum.TICKET_SUBMIT.value,
        None,
    ),

    # --- 第 7 层：多步流程 ---
    (
        r"(帮.*所有|升级.*套餐|执行.*步骤|依次|逐个|逐步)",
        IntentEnum.MULTI_STEP_FLOW.value,
        None,
    ),
]


def _get_last_human_message_content(state: AgentState) -> str:
    """从 state["messages"] 中获取最后一条 HumanMessage 的文本内容。"""
    messages = state.get("messages", [])
    for msg in reversed(messages):
        # LangChain HumanMessage 的 type 属性为 "human"
        msg_type = getattr(msg, "type", "")
        if msg_type == "human" or msg.__class__.__name__ == "HumanMessage":
            content = getattr(msg, "content", "")
            if isinstance(content, str):
                return content
            # content 可能是 list（多模态），取文本部分
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        return part.get("text", "")
                    if isinstance(part, str):
                        return part
    return ""


def _regex_classify(text: str) -> tuple[str, float, dict] | None:
    """正则匹配意图分类。

    Returns:
        (intent_label, confidence, entities) 或 None（未命中）
    """
    for pattern, intent, entities_extractor in INTENT_REGEX_RULES:
        if re.search(pattern, text, re.IGNORECASE):
            entities = entities_extractor or {}
            return (intent, 1.0, entities)
    return None


async def _llm_classify(text: str, llm: Any) -> tuple[str, float, dict]:
    """LLM fallback 意图分类（单 token 输出）。

    Returns:
        (intent_label, confidence, entities)
    """
    from app.agent.prompts import INTENT_CLASSIFICATION_PROMPT

    prompt = INTENT_CLASSIFICATION_PROMPT.format(user_message=text)
    try:
        response = await llm.ainvoke(prompt)
        # 提取意图标签（LLM 可能输出带换行或空格）
        content = response.content if hasattr(response, "content") else str(response)
        content = content.strip().lower()

        # 验证输出是有效的意图标签
        valid_intents = [e.value for e in IntentEnum]
        for intent_val in valid_intents:
            if intent_val in content:
                return (intent_val, 0.8, {})

        # 未识别，默认 chat
        logger.warning("LLM intent classification fallback to chat: %s", content)
        return (IntentEnum.CHAT.value, 0.5, {})
    except Exception as e:
        logger.error("LLM intent classification failed: %s", e)
        return (IntentEnum.CHAT.value, 0.3, {})


def create_intent_parser_node(llm: Any = None):
    """创建 IntentParser 节点函数。

    Args:
        llm: 可选的 LLM 实例，用于正则未命中时的 fallback 分类

    Returns:
        异步节点函数，输入 AgentState，输出 state 更新 dict
    """

    async def intent_parser_node(state: AgentState) -> dict:
        """意图分类节点。

        1. 从 messages 获取最后一条用户消息
        2. 遍历正则规则表（优先级从高到低）
        3. 命中 → 返回 intent + confidence=1.0 + method=regex
        4. 未命中 → 调用 LLM 分类（如果 llm 可用）
        """
        text = _get_last_human_message_content(state)

        if not text:
            return {
                "intent": {
                    "intent_label": IntentEnum.CHAT.value,
                    "confidence": 0.5,
                    "method": "empty",
                    "entities": {},
                }
            }

        # 正则匹配
        result = _regex_classify(text)
        if result:
            intent_label, confidence, entities = result
            logger.debug(
                "Intent regex matched: %s -> %s (conf=%.1f)",
                text[:50],
                intent_label,
                confidence,
            )
            return {
                "intent": {
                    "intent_label": intent_label,
                    "confidence": confidence,
                    "method": "regex",
                    "entities": entities,
                }
            }

        # LLM fallback
        if llm is not None:
            intent_label, confidence, entities = await _llm_classify(text, llm)
            logger.debug(
                "Intent LLM classified: %s -> %s (conf=%.1f)",
                text[:50],
                intent_label,
                confidence,
            )
            return {
                "intent": {
                    "intent_label": intent_label,
                    "confidence": confidence,
                    "method": "llm",
                    "entities": entities,
                }
            }

        # 无 LLM 可用，默认 chat
        return {
            "intent": {
                "intent_label": IntentEnum.CHAT.value,
                "confidence": 0.3,
                "method": "default",
                "entities": {},
            }
        }

    return intent_parser_node
