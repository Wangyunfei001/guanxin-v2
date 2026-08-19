"""Agent 状态定义模块。

定义 AgentState TypedDict、IntentEnum、ModeEnum，
用于自定义 StateGraph 的状态管理。
"""

from enum import Enum
from typing import Annotated, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class IntentEnum(str, Enum):
    """意图枚举（10 种意图）。"""

    CHAT = "chat"                           # 闲聊/问候
    KNOWLEDGE_QUERY = "knowledge_query"      # 知识库问答
    DATA_QUERY = "data_query"               # 数据查询
    SINGLE_CREATE = "single_create"          # 单条创建
    SINGLE_UPDATE = "single_update"          # 单条更新
    SINGLE_DELETE = "single_delete"          # 单条删除
    BATCH_OPERATION = "batch_operation"      # 批量操作
    MULTI_STEP_FLOW = "multi_step_flow"      # 多步流程
    SYSTEM_DIAGNOSIS = "system_diagnosis"    # 系统诊断
    TICKET_SUBMIT = "ticket_submit"          # 工单提报


class ModeEnum(str, Enum):
    """交互模式枚举（P0 三种模式）。"""

    CHAT = "chat"        # 自由对话，无工具调用
    DIRECT = "direct"    # 直接执行工具
    CONFIRM = "confirm"  # 需用户确认后执行
    # P1 扩展:
    # FORM = "form"             # 弹表单补全参数
    # MULTI_STEP = "multi_step"  # 多步编排


class IntentSubState(TypedDict):
    """意图分类结果子状态。"""

    intent_label: str       # 意图标签（IntentEnum 值之一）
    confidence: float       # 置信度 0.0~1.0
    method: str             # 分类方法："regex" | "llm"
    entities: dict          # 提取的实体，如 {"target": "租户", "name": "tenant-a"}


class ContextSubState(TypedDict):
    """执行上下文子状态。"""

    tenant_id: str
    user_id: str
    conversation_id: str
    agent_id: str


class ToolsSubState(TypedDict):
    """工具相关子状态。"""

    enabled_tool_names: list[str]        # 用户配置启用的工具名列表
    available_tools: list[dict]          # 运行时可用工具元数据（动态更新）


class AgentState(TypedDict):
    """Agent 主状态，用于 StateGraph 生命周期。

    messages 使用 LangGraph 的 add_messages reducer 自动合并。
    子状态用 TypedDict 分组，LangGraph 内部以平铺 key 方式更新。
    """

    # 消息列表（LangGraph add_messages reducer 自动合并）
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # 子状态分组
    intent: IntentSubState               # 意图分类结果
    context: ContextSubState             # 执行上下文
    tools_state: ToolsSubState           # 工具状态

    # 顶层路由键
    mode: str                            # 交互模式："chat" | "direct" | "confirm"
    confirmed: bool                      # confirm 模式下用户是否已确认

    # 输出
    final_response: str                  # 最终回复文本
