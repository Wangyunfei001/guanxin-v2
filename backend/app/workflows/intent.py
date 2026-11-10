"""Deterministic business workflow triggers.

这里的正则只用于**选择计划形态**（确定性单步 vs LLM 规划），不再决定
「要不要发起工作流」——发起工作流只有两个入口：Agent 的
``request_business_workflow`` 工具，和工作流引擎本身。
"""

import re

# 问句标记：命中则说明用户在问「怎么做」，而不是「帮我做」。
# 问句绝不产生变更类意图，避免「如何删除用户」被路由成删除工作流。
QUESTION_MARKERS: tuple[str, ...] = (
    "什么",
    "如何",
    "怎么",
    "怎样",
    "为什么",
    "为何",
    "是什么",
    "什么是",
    "啥是",
    "能不能",
    "能否",
    "可不可以",
    "是否",
    "请问",
    "介绍",
    "解释",
    "说明一下",
    "有哪些",
    "吗",
    "呢",
    "？",
    "?",
)


def looks_like_question(text: str) -> bool:
    """判断文本是否是问句而不是祈使请求。"""
    stripped = text.strip()
    if not stripped:
        return False
    if stripped.endswith(("？", "?")):
        return True
    return any(marker in stripped for marker in QUESTION_MARKERS)


INTENT_REGEX_RULES: list[tuple[str, str, dict | None]] = [
    # --- 第 -1 层：确认/取消协议消息（最高优先级，防止 LLM 误分类）---
    (
        r"^✅ 确认操作：",
        'chat',  # 实际路由由 mode_decision 接管
        None,
    ),
    (
        r"^取消操作：",
        'chat',  # 实际路由由 mode_decision 接管
        None,
    ),

    # --- 第 0 层：闲聊、打招呼（最高优先级）---
    (
        r"^(你好|hi|hello|嗨|早上好|晚上好|下午好|好久不见|在吗|嘿|hello there)",
        'chat',
        None,
    ),

    # --- 第 1 层：知识类问句 ---
    (
        r"(什么是|什么叫|啥是|介绍.*一下|.*是什么概念|.*是什么意思|.*的定义)",
        'knowledge_query',
        None,
    ),
    (
        r"(知识库|知识.*文档|上传.*文档).*(怎么|如何|怎样)",
        'knowledge_query',
        None,
    ),

    # --- 第 2 层：数据查询 ---
    (
        r"(查询|查看|列出|显示|有哪些|搜索|检索|找一下).*(租户|用户|账号|权限|角色|日志|任务|skill|技能)",
        'data_query',
        None,
    ),
    (
        r"^(查|搜).*(租户|用户|列表|skill|技能)",
        'data_query',
        None,
    ),

    # --- 第 3 层：单条 CRUD ---
    (
        r"(新增|创建|添加|新建|开通|注册).*(租户|用户|账号|项目|空间)",
        'single_create',
        None,
    ),
    (
        r"(修改|更新|编辑|更改|重命名|调整|配置).*(租户|用户|账号|项目|设置|名称)",
        'single_update',
        None,
    ),
    (
        r"(删除|移除|注销|停用|禁用|清理).*(租户|用户|账号|项目)",
        'single_delete',
        None,
    ),

    # --- 第 4 层：批量操作 ---
    (
        r"(批量|导入|导出|迁移|同步|全部.*升级|全部.*更新)",
        'batch_operation',
        None,
    ),

    # --- 第 5 层：系统诊断 ---
    (
        r"(系统.*慢|为什么.*慢|排查|诊断|性能|日志.*报错|看.*日志|检查.*状态)",
        'system_diagnosis',
        None,
    ),

    # --- 第 6 层：工单 ---
    (
        r"(工单|报错|故障|bug|问题反馈|提个.*issue|提交.*问题)",
        'ticket_submit',
        None,
    ),

    # --- 第 7 层：多步流程 ---
    (
        r"(帮.*所有|升级.*套餐|执行.*步骤|依次|逐个|逐步)",
        'multi_step_flow',
        None,
    ),
]


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
