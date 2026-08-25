"""DeepSeek-backed linear workflow planner with server-side validation."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.agent.graph import _create_llm
from app.agent.nodes.intent_parser import _regex_classify
from app.models.agent import AgentConfig
from app.workflows.catalog import WorkflowToolError, normalize_arguments
from app.workflows.models import WorkflowPlan, WorkflowPlanStep, WorkflowTool


WORKFLOW_INTENTS = {
    "single_create",
    "single_update",
    "single_delete",
    "batch_operation",
}


class WorkflowPlannerError(RuntimeError):
    pass


def detect_workflow_intent(text: str) -> str:
    """Return only explicit mutating intents that require a durable workflow."""
    classified = _regex_classify(text)
    if classified and classified[0] in WORKFLOW_INTENTS:
        return classified[0]
    return ""


def _walk_references(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, str) and value.startswith("$steps."):
        refs.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            refs.extend(_walk_references(item))
    elif isinstance(value, list):
        for item in value:
            refs.extend(_walk_references(item))
    return refs


def validate_and_normalize_plan(
    plan: WorkflowPlan,
    catalog: list[WorkflowTool],
) -> tuple[WorkflowPlan, list[dict[str, Any]]]:
    tools = {item.name: item for item in catalog}
    previous: set[str] = set()
    persisted_steps: list[dict[str, Any]] = []
    normalized_steps: list[WorkflowPlanStep] = []
    for step in plan.steps:
        tool = tools.get(step.tool_name)
        if tool is None:
            raise WorkflowPlannerError(f"计划引用了未授权或不存在的工具: {step.tool_name}")
        try:
            arguments = normalize_arguments(tool, step.arguments)
        except WorkflowToolError as exc:
            raise WorkflowPlannerError(str(exc)) from exc
        for reference in _walk_references(arguments):
            pieces = reference.split(".")
            if len(pieces) < 3 or pieces[1] not in previous:
                raise WorkflowPlannerError(f"步骤 {step.step_id} 包含非法前序引用: {reference}")
        normalized_steps.append(step.model_copy(update={"arguments": arguments}))
        persisted_steps.append(
            {
                "step_id": step.step_id,
                "title": step.title,
                "tool_name": step.tool_name,
                "tool_category": tool.category,
                "arguments": arguments,
                "risk": tool.risk,
            }
        )
        previous.add(step.step_id)
    return plan.model_copy(update={"steps": normalized_steps}), persisted_steps


def deterministic_single_step(intent: str, user_message: str) -> WorkflowPlan:
    mapping = {
        "single_create": ("skill__create_user", "创建用户"),
        "single_update": ("skill__update_user", "更新用户"),
        "single_delete": ("skill__delete_user", "删除用户"),
        "batch_operation": ("skill__export_data", "导出数据"),
    }
    tool_name, title = mapping[intent]
    return WorkflowPlan(
        goal=user_message,
        summary=f"执行单步操作：{title}",
        steps=[
            WorkflowPlanStep(
                step_id="step_1",
                title=title,
                tool_name=tool_name,
                arguments={},
            )
        ],
    )


def _planner_prompt(user_message: str, catalog: list[WorkflowTool], repair: str = "") -> str:
    tools_json = json.dumps(
        [item.model_dump() for item in catalog], ensure_ascii=False, indent=2
    )
    repair_text = f"\n上一次计划校验失败：{repair}\n请修复后重新输出。" if repair else ""
    return f"""你是观心 v2 的工作流规划器。请把用户目标拆成可执行的线性工具步骤。

规则：
1. 只能使用下方工具，最多 16 步，不得编造工具或参数。
2. step_id 使用 step_1、step_2 的稳定格式且必须唯一。
3. 缺少的用户输入写成 $inputs.<参数名>。
4. 只能用 $steps.<前序step_id>.<结果路径> 引用已经执行的步骤。
5. 不要判断权限和风险，服务端会处理。
6. 只输出符合 WorkflowPlan schema 的结构化结果。

用户目标：{user_message}

可用工具：
{tools_json}
{repair_text}"""


async def create_workflow_plan(
    user_message: str,
    intent: str,
    config: AgentConfig,
    catalog: list[WorkflowTool],
) -> tuple[WorkflowPlan, list[dict[str, Any]]]:
    if intent in {"single_create", "single_update", "single_delete", "batch_operation"}:
        return validate_and_normalize_plan(
            deterministic_single_step(intent, user_message), catalog
        )
    if not catalog:
        raise WorkflowPlannerError("当前 Agent 没有可用于工作流的工具")
    llm = _create_llm(config.model, config.temperature, config.max_tokens)
    if llm is None:
        raise WorkflowPlannerError("未配置可用的大模型，无法生成工作流计划")
    # DeepSeek's OpenAI-compatible endpoint currently rejects the JSON Schema
    # response_format used by LangChain's default method. Tool calling still
    # gives us typed output, followed by the same server-side Pydantic checks.
    structured = llm.with_structured_output(WorkflowPlan, method="function_calling")
    last_error = ""
    for attempt in range(2):
        try:
            raw = await structured.ainvoke(
                _planner_prompt(user_message, catalog, last_error if attempt else "")
            )
            plan = raw if isinstance(raw, WorkflowPlan) else WorkflowPlan.model_validate(raw)
            return validate_and_normalize_plan(plan, catalog)
        except (ValidationError, WorkflowPlannerError, Exception) as exc:
            last_error = str(exc)
            if attempt == 1:
                raise WorkflowPlannerError(f"计划生成失败: {last_error}") from exc
    raise WorkflowPlannerError("计划生成失败")
