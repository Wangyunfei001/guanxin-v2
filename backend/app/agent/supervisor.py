"""Structured request routing for the unified Agent execution chain."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.agent.nodes.intent_parser import _regex_classify
from app.agent.tool_catalog import CatalogEntry, catalog_prompt
from app.models.agent import AgentConfig


class RouteDecision(BaseModel):
    route: Literal["respond", "tool_loop", "research", "write_workflow"]
    required_capabilities: list[str] = Field(default_factory=list)
    candidate_tools: list[str] = Field(default_factory=list, max_length=8)
    estimated_steps: int = Field(default=1, ge=0, le=16)
    research_mode: Literal["auto", "quick", "deep"] = "auto"
    reason: str = ""


WRITE_INTENTS = {
    "single_create",
    "single_update",
    "single_delete",
    "batch_operation",
}
CHAT_PATTERN = re.compile(
    r"^(你好|hi|hello|嗨|早上好|晚上好|下午好|谢谢|感谢|你是谁|在吗)[！!。,.，\s]*$",
    re.IGNORECASE,
)
DEEP_RESEARCH_PATTERN = re.compile(
    r"(深入研究|深度研究|全面调研|系统性研究|完整研究报告|deep\s*research)",
    re.IGNORECASE,
)
QUICK_RESEARCH_PATTERN = re.compile(
    r"(最新|近期|今天.*新闻|新闻|全网|网上|网页|搜索引擎|多来源|实时信息|公开资料|调研)",
    re.IGNORECASE,
)


def _find_names(entries: list[CatalogEntry], predicate: Any) -> list[str]:
    return [entry.spec.name for entry in entries if predicate(entry)]


def deterministic_route(
    user_message: str,
    entries: list[CatalogEntry],
    research_mode: str = "auto",
) -> RouteDecision | None:
    """Apply only high-confidence safety and capability rules."""
    classified = _regex_classify(user_message)
    if classified and classified[0] in WRITE_INTENTS:
        return RouteDecision(
            route="write_workflow",
            required_capabilities=[classified[0]],
            estimated_steps=1,
            reason="明确写操作由服务端强制进入审批工作流",
        )

    if CHAT_PATTERN.search(user_message.strip()):
        return RouteDecision(route="respond", estimated_steps=0, reason="明确闲聊")

    research_enabled = any(entry.spec.name == "deep_research" for entry in entries)
    if research_enabled and (research_mode == "deep" or DEEP_RESEARCH_PATTERN.search(user_message)):
        return RouteDecision(
            route="research",
            required_capabilities=["web_search"],
            candidate_tools=["deep_research"],
            estimated_steps=5,
            research_mode="deep",
            reason="用户显式要求深度研究",
        )
    if research_enabled and research_mode == "quick":
        return RouteDecision(
            route="research",
            required_capabilities=["web_search"],
            candidate_tools=["deep_research"],
            estimated_steps=2,
            research_mode="quick",
            reason="用户显式选择快速研究",
        )

    message = user_message.lower()
    if re.search(r"(天气|气温|温度|下雨|降雨|空气质量|风速|湿度)", message):
        candidates = _find_names(
            entries,
            lambda entry: entry.spec.effect == "read"
            and entry.spec.source_type == "mcp"
            and (
                "weather" in entry.spec.name.lower()
                or "天气" in entry.spec.description
            ),
        )
        if candidates:
            return RouteDecision(
                route="tool_loop",
                required_capabilities=["weather"],
                candidate_tools=candidates[:1],
                estimated_steps=1,
                reason="天气请求唯一匹配只读 MCP 工具",
            )

    if re.search(r"(分析|平均|均值|中位数|标准差|最大值|最小值)", message):
        candidates = _find_names(entries, lambda entry: entry.spec.name == "skill__data_analysis")
        if candidates:
            return RouteDecision(
                route="tool_loop",
                required_capabilities=["data_analysis"],
                candidate_tools=candidates,
                estimated_steps=1,
                reason="数据分析请求匹配只读 Skill",
            )

    if re.search(r"(摘要|总结|提炼|概括)", message):
        candidates = _find_names(entries, lambda entry: entry.spec.name == "skill__text_summary")
        if candidates:
            return RouteDecision(
                route="tool_loop",
                required_capabilities=["text_summary"],
                candidate_tools=candidates,
                estimated_steps=1,
                reason="摘要请求匹配只读 Skill",
            )

    if re.search(r"(知识库|文档|资料库|根据.*资料|从.*文档)", message):
        candidates = _find_names(entries, lambda entry: entry.spec.name == "kb_retrieval")
        if candidates:
            return RouteDecision(
                route="tool_loop",
                required_capabilities=["knowledge"],
                candidate_tools=candidates,
                estimated_steps=1,
                reason="知识库请求匹配检索工具",
            )

    if research_enabled and QUICK_RESEARCH_PATTERN.search(user_message):
        return RouteDecision(
            route="research",
            required_capabilities=["web_search"],
            candidate_tools=["deep_research"],
            estimated_steps=2,
            research_mode="quick",
            reason="请求需要新鲜或多来源公开信息",
        )
    return None


def _validate_decision(
    decision: RouteDecision,
    entries: list[CatalogEntry],
    requested_mode: str,
) -> RouteDecision:
    visible = {entry.spec.name: entry for entry in entries}
    validated = [name for name in decision.candidate_tools if name in visible][:8]
    if decision.route == "tool_loop":
        validated = [
            name
            for name in validated
            if visible[name].spec.effect == "read"
            and not visible[name].spec.approval_required
            and visible[name].tool is not None
        ]
        if not validated:
            return RouteDecision(route="respond", reason="未找到可自动执行的授权只读工具")
    if decision.route == "research" and "deep_research" not in visible:
        return RouteDecision(route="respond", reason="当前 Agent 未启用 Deep Research")
    if decision.route == "write_workflow":
        return decision.model_copy(update={"candidate_tools": []})
    mode = decision.research_mode
    if mode == "deep" and requested_mode != "deep":
        mode = "quick"
    return decision.model_copy(update={"candidate_tools": validated, "research_mode": mode})


async def decide_route(
    user_message: str,
    config: AgentConfig,
    entries: list[CatalogEntry],
    *,
    research_mode: str = "auto",
    llm: Any = None,
) -> RouteDecision:
    effective_mode = (
        "deep"
        if research_mode == "deep" or DEEP_RESEARCH_PATTERN.search(user_message)
        else research_mode
    )
    deterministic = deterministic_route(user_message, entries, research_mode)
    if deterministic is not None:
        return _validate_decision(deterministic, entries, effective_mode)

    if llm is None:
        from app.agent.graph import _create_llm

        llm = _create_llm(config.model, 0, min(config.max_tokens, 2048))
    if llm is None:
        return RouteDecision(route="respond", reason="Supervisor 模型不可用")

    prompt = f"""你是观心的请求 Supervisor。只负责选择执行路径，不回答用户问题。

路径：
- respond：无需外部数据的普通回答。
- tool_loop：使用一个或多个已授权只读工具。
- research：需要公开互联网的新鲜信息或多来源研究。
- write_workflow：任何创建、修改、删除、导出或其他有副作用的任务。

规则：
1. 只能选择工具目录中存在的名称，最多 8 个。
2. 不要把普通句子中的“并且、然后”当成工作流依据。
3. write 或 unknown 风险能力必须走 write_workflow。
4. deep 研究只有用户显式要求时才能选择；否则 research_mode=quick。
5. estimated_steps 估算需要的工具步骤数。

用户请求：{user_message}
用户选择的研究模式：{research_mode}

工具目录：
{catalog_prompt(entries)}
"""
    try:
        structured = llm.with_structured_output(RouteDecision, method="function_calling")
        raw = await structured.ainvoke(prompt)
        decision = raw if isinstance(raw, RouteDecision) else RouteDecision.model_validate(raw)
        return _validate_decision(decision, entries, effective_mode)
    except Exception:
        read_tools = [
            entry.spec.name
            for entry in entries
            if entry.tool is not None
            and entry.spec.effect == "read"
            and not entry.spec.approval_required
        ]
        if len(read_tools) == 1:
            return RouteDecision(
                route="tool_loop",
                candidate_tools=read_tools,
                estimated_steps=1,
                reason="Supervisor 失败后使用唯一授权只读工具",
            )
        return RouteDecision(route="respond", reason="Supervisor 失败，安全回退为直接回答")
