"""Persistent, interruptible linear workflow execution engine."""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from langchain_core.runnables import RunnableConfig

from app.core.checkpoints import (
    delete_checkpoint_thread,
    get_checkpointer,
    initialize_checkpointer,
)
from app.models.agent import get_agent_config_store
from app.models.skill_context import SkillContext
from app.services.workflow_store import WorkflowConflictError, get_workflow_store
from app.workflows.catalog import (
    WorkflowToolError,
    catalog_by_name,
    execute_tool,
    input_fields,
    resolve_arguments,
)
from app.workflows.planner import WorkflowPlannerError, create_workflow_plan

logger = logging.getLogger(__name__)


class WorkflowState(TypedDict, total=False):
    run_id: str
    inputs: dict[str, Any]


def _runtime(config: RunnableConfig) -> tuple[str, str, str]:
    configurable = config.get("configurable", {})
    return (
        str(configurable.get("tenant_id", "")),
        str(configurable.get("user_id", "")),
        str(configurable.get("user_role", "user")),
    )


def _run_config(run_id: str, tenant_id: str, user_id: str, user_role: str) -> dict:
    return {
        "configurable": {
            "thread_id": run_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "user_role": user_role,
        },
        "recursion_limit": 50,
    }


async def _execute_step_node(state: WorkflowState, config: RunnableConfig) -> dict:
    store = get_workflow_store()
    run_id = state["run_id"]
    tenant_id, user_id, user_role = _runtime(config)
    run = store.get_run(run_id, tenant_id, user_id)
    if run is None:
        raise PermissionError("工作流不存在或无权访问")
    if run["status"] in {"completed", "cancelled", "failed"}:
        return state
    index = run["current_step_index"]
    if index >= len(run["steps"]):
        store.set_run_status(run_id, "completed", current_step_index=index)
        return state

    step = run["steps"][index]
    agent_config = get_agent_config_store().get_config(tenant_id, run["agent_id"])
    if agent_config is None:
        store.set_run_status(run_id, "failed", error="Agent 配置不存在")
        return state
    catalog = catalog_by_name(agent_config, user_role)
    tool = catalog.get(step["tool_name"])
    if tool is None:
        store.set_run_status(run_id, "failed", error="工具已禁用或当前用户无权执行")
        store.update_step(step["db_step_id"], status="failed", error="工具不可用")
        return state

    outputs = {
        item["step_id"]: item["result"]
        for item in run["steps"][:index]
        if item["status"] == "completed"
    }
    inputs = dict(state.get("inputs", {}))
    resolved, missing = resolve_arguments(
        step["arguments"], inputs=inputs, outputs=outputs
    )
    if missing:
        interrupt_id = f"input_{run_id}_{step['step_id']}"
        fields = input_fields(tool, missing)
        store.create_interrupt(
            run_id,
            step["db_step_id"],
            "input",
            {"title": f"补充参数：{step['title']}", "fields": fields},
            interrupt_id,
        )
        store.update_step(step["db_step_id"], status="waiting_input")
        store.set_run_status(run_id, "waiting_input", current_step_index=index)
        response = interrupt(
            {
                "interrupt_id": interrupt_id,
                "run_id": run_id,
                "step_id": step["step_id"],
                "kind": "input",
                "title": f"补充参数：{step['title']}",
                "fields": fields,
            }
        )
        if not isinstance(response, dict) or not response.get("accepted"):
            store.cancel(run_id)
            return {**state, "inputs": inputs}
        inputs.update(response.get("values") or {})
        resolved, missing = resolve_arguments(
            step["arguments"], inputs=inputs, outputs=outputs
        )
        if missing:
            store.set_run_status(run_id, "failed", error="提交的参数仍不完整")
            store.update_step(step["db_step_id"], status="failed", error="参数不完整")
            return {**state, "inputs": inputs}

    if tool.risk != "read":
        interrupt_id = f"approval_{run_id}_{step['step_id']}"
        store.create_interrupt(
            run_id,
            step["db_step_id"],
            "approval",
            {
                "title": f"确认执行：{step['title']}",
                "tool_name": tool.name,
                "arguments": resolved,
                "risk": tool.risk,
            },
            interrupt_id,
        )
        store.update_step(
            step["db_step_id"],
            status="waiting_approval",
            resolved_arguments=resolved,
        )
        store.set_run_status(run_id, "waiting_approval", current_step_index=index)
        response = interrupt(
            {
                "interrupt_id": interrupt_id,
                "run_id": run_id,
                "step_id": step["step_id"],
                "kind": "approval",
                "title": f"确认执行：{step['title']}",
                "tool_name": tool.name,
                "arguments": resolved,
                "risk": tool.risk,
            }
        )
        if not isinstance(response, dict) or not response.get("accepted"):
            store.cancel(run_id)
            return {**state, "inputs": inputs}

    execution_id, saved_result = store.begin_execution(run_id, step["db_step_id"])
    if execution_id == "completed":
        store.set_run_status(run_id, "running", current_step_index=index + 1)
        return {**state, "inputs": inputs}
    try:
        result = await execute_tool(
            tool,
            resolved,
            SkillContext(
                tenant_id=tenant_id,
                user_id=user_id,
                user_role=user_role,
                conversation_id=run["conversation_id"],
                metadata={"workflow_run_id": run_id, "workflow_step_id": step["step_id"]},
            ),
        )
    except PermissionError as exc:
        store.finish_execution(
            execution_id, run_id, step["db_step_id"], status="failed", error=str(exc)
        )
        store.set_run_status(run_id, "failed", error=str(exc))
        raise
    except Exception as exc:
        message = str(exc)
        store.finish_execution(
            execution_id, run_id, step["db_step_id"], status="failed", error=message
        )
        refreshed = store.get_run(run_id)
        attempts = refreshed["steps"][index]["attempt_count"] if refreshed else 2
        if tool.risk == "read" and attempts < 2:
            store.update_step(step["db_step_id"], status="pending", error=message)
            store.set_run_status(run_id, "running", current_step_index=index, error=message)
            return {**state, "inputs": inputs}
        store.set_run_status(run_id, "failed", current_step_index=index, error=message)
        return {**state, "inputs": inputs}

    store.finish_execution(
        execution_id,
        run_id,
        step["db_step_id"],
        status="completed",
        result=result,
    )
    next_index = index + 1
    refreshed = store.get_run(run_id)
    status = "completed" if refreshed and next_index >= len(refreshed["steps"]) else "running"
    store.set_run_status(run_id, status, current_step_index=next_index)
    return {**state, "inputs": inputs}


def _route_after_step(state: WorkflowState) -> str:
    run = get_workflow_store().get_run(state["run_id"])
    if run and run["status"] == "running" and run["current_step_index"] < len(run["steps"]):
        return "continue"
    return "end"


_workflow_graph = None


def get_workflow_graph():
    global _workflow_graph
    if _workflow_graph is not None:
        return _workflow_graph
    builder = StateGraph(WorkflowState)
    builder.add_node("execute_step", _execute_step_node)
    builder.add_edge(START, "execute_step")
    builder.add_conditional_edges(
        "execute_step",
        _route_after_step,
        {"continue": "execute_step", "end": END},
    )
    _workflow_graph = builder.compile(checkpointer=get_checkpointer())
    return _workflow_graph


def reset_workflow_graph() -> None:
    global _workflow_graph
    _workflow_graph = None


async def start_workflow(
    *,
    user_message: str,
    intent: str,
    tenant_id: str,
    user_id: str,
    user_role: str,
    conversation_id: str,
    agent_id: str,
) -> dict[str, Any]:
    await initialize_checkpointer()
    config = get_agent_config_store().get_config(tenant_id, agent_id)
    if config is None:
        raise WorkflowPlannerError("Agent 配置不存在")
    catalog = list(catalog_by_name(config, user_role).values())
    plan, steps = await create_workflow_plan(user_message, intent, config, catalog)
    store = get_workflow_store()
    run = store.create_run(
        tenant_id=tenant_id,
        user_id=user_id,
        conversation_id=conversation_id,
        agent_id=agent_id,
        goal=plan.goal,
        summary=plan.summary,
        plan=plan.model_dump(),
        steps=steps,
    )
    try:
        await get_workflow_graph().ainvoke(
            {"run_id": run["run_id"], "inputs": {}},
            config=_run_config(run["run_id"], tenant_id, user_id, user_role),
        )
    except Exception as exc:
        logger.exception("Workflow start failed: %s", run["run_id"])
        store.set_run_status(run["run_id"], "failed", error=str(exc))
    return store.get_run(run["run_id"], tenant_id, user_id) or run


async def resume_workflow(
    *,
    interrupt_id: str,
    accepted: bool,
    values: dict[str, Any],
    tenant_id: str,
    user_id: str,
    user_role: str,
) -> dict[str, Any]:
    await initialize_checkpointer()
    store = get_workflow_store()
    interrupt_row = store.get_interrupt(interrupt_id)
    if interrupt_row is None:
        raise LookupError("工作流中断不存在")
    run = store.get_run(interrupt_row["run_id"], tenant_id, user_id)
    if run is None:
        raise LookupError("工作流不存在")
    if interrupt_row["status"] != "pending":
        return run
    store.resolve_interrupt(
        interrupt_id,
        run["run_id"],
        accepted=accepted,
        response={"accepted": accepted, "values": values},
    )
    await get_workflow_graph().ainvoke(
        Command(resume={"accepted": accepted, "values": values}),
        config=_run_config(run["run_id"], tenant_id, user_id, user_role),
    )
    return store.get_run(run["run_id"], tenant_id, user_id) or run


async def resolve_uncertain_workflow(
    *,
    run: dict[str, Any],
    action: str,
    result_summary: str,
    tenant_id: str,
    user_id: str,
    user_role: str,
) -> dict[str, Any]:
    await initialize_checkpointer()
    store = get_workflow_store()
    if run["status"] != "uncertain":
        raise WorkflowConflictError("工作流不处于 uncertain 状态")
    step = run["steps"][run["current_step_index"]]
    if action == "cancel":
        store.cancel(run["run_id"])
        await delete_checkpoint_thread(run["run_id"])
        return store.get_run(run["run_id"], tenant_id, user_id) or run
    if step["risk"] != "read" and user_role != "admin":
        raise PermissionError("风险步骤仅管理员可处理")
    if action == "mark_completed":
        result = {"success": True, "output": {"manual_summary": result_summary}}
        store.update_step(step["db_step_id"], status="completed", result=result)
        store.set_run_status(
            run["run_id"], "running", current_step_index=run["current_step_index"] + 1
        )
    elif action == "retry":
        store.update_step(step["db_step_id"], status="pending", error="")
        store.set_run_status(
            run["run_id"], "running", current_step_index=run["current_step_index"]
        )
    else:
        raise ValueError("不支持的处理动作")
    await delete_checkpoint_thread(run["run_id"])
    await get_workflow_graph().ainvoke(
        {"run_id": run["run_id"], "inputs": {}},
        config=_run_config(run["run_id"], tenant_id, user_id, user_role),
    )
    return store.get_run(run["run_id"], tenant_id, user_id) or run
