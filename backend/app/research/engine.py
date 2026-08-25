"""Budgeted, persistent Deep Research execution engine."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from app.agent.tool_catalog import CatalogEntry
from app.config import settings
from app.research.provider import DeepSeekResearchProvider
from app.services.research_store import get_research_store


def research_budget(mode: str) -> dict[str, int]:
    if mode == "deep":
        return {
            "max_rounds": settings.research_deep_rounds,
            "max_searches": settings.research_deep_searches,
            "max_sources": settings.research_deep_sources,
            "timeout_seconds": settings.research_deep_timeout_seconds,
        }
    return {
        "max_rounds": settings.research_quick_rounds,
        "max_searches": settings.research_quick_searches,
        "max_sources": settings.research_quick_sources,
        "timeout_seconds": settings.research_quick_timeout_seconds,
    }


def public_research_snapshot(run: dict[str, Any]) -> dict[str, Any]:
    return {
        key: run[key]
        for key in (
            "run_id",
            "conversation_id",
            "mode",
            "status",
            "goal",
            "plan",
            "budget",
            "usage",
            "report",
            "error",
            "tasks",
            "sources",
            "created_at",
            "updated_at",
        )
        if key in run
    }


def _cancelled(run_id: str) -> bool:
    run = get_research_store().get_run(run_id)
    return run is None or run["status"] == "cancelled"


async def run_research(
    *,
    tenant_id: str,
    user_id: str,
    conversation_id: str,
    goal: str,
    mode: str,
    catalog: list[CatalogEntry],
    provider: DeepSeekResearchProvider | None = None,
    resume_run_id: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    store = get_research_store()
    provider = provider or DeepSeekResearchProvider()
    budget = research_budget(mode)
    if resume_run_id:
        run = store.get_run(resume_run_id, tenant_id, user_id)
        if run is None:
            raise ValueError("Research 运行不存在")
        run_id = resume_run_id
        mode = run["mode"]
        budget = run["budget"] or research_budget(mode)
        store.set_status(run_id, "planning", error="")
    else:
        run = store.create_run(
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=conversation_id,
            mode=mode,
            goal=goal,
            budget=budget,
        )
        run_id = run["run_id"]

    yield public_research_snapshot(store.get_run(run_id) or run)

    persisted_usage = (store.get_run(run_id) or {}).get("usage", {})
    usage: dict[str, Any] = {
        "search_actions": int(persisted_usage.get("search_actions", 0) or 0),
        "tool_calls": int(persisted_usage.get("tool_calls", 0) or 0),
        "sources": len((store.get_run(run_id) or {}).get("sources", [])),
        "input_tokens": int(persisted_usage.get("input_tokens", 0) or 0),
        "output_tokens": int(persisted_usage.get("output_tokens", 0) or 0),
    }
    evidence: list[dict[str, Any]] = []
    runtime_by_name = {
        entry.spec.name: entry
        for entry in catalog
        if entry.tool is not None
        and entry.spec.effect == "read"
        and not entry.spec.approval_required
    }

    async def execute() -> AsyncIterator[dict[str, Any]]:
        current = store.get_run(run_id) or {}
        if not current.get("tasks"):
            initial_questions = min(
                int(budget["max_searches"]),
                2 if mode == "quick" else 4,
            )
            plan = await provider.plan(
                goal,
                mode,
                [entry.spec for entry in catalog],
                initial_questions,
            )
            store.set_plan(
                run_id,
                plan.model_dump(),
                [item.question for item in plan.questions],
            )
            current = store.get_run(run_id) or current
        else:
            plan_data = current.get("plan") or {}
            from app.research.models import ResearchPlan

            plan = ResearchPlan.model_validate(plan_data)

        planned_by_question = {item.question: item for item in plan.questions}
        for task in current.get("tasks", []):
            if task["status"] == "completed":
                if task.get("result_summary"):
                    evidence.append({"question": task["question"], "answer": task["result_summary"]})

        for round_index in range(int(budget["max_rounds"])):
            pending = [
                task
                for task in (store.get_run(run_id) or {}).get("tasks", [])
                if task["status"] in {"pending", "failed"}
            ]
            if not pending or usage["search_actions"] >= int(budget["max_searches"]):
                break
            store.set_status(run_id, "searching", usage=usage)
            yield public_research_snapshot(store.get_run(run_id) or {})

            for task in pending:
                if _cancelled(run_id):
                    return
                if usage["search_actions"] >= int(budget["max_searches"]):
                    break
                store.update_task(task["task_id"], "searching", increment_attempt=True)
                planned = planned_by_question.get(task["question"])
                local_results: list[dict[str, Any]] = []
                for call in planned.tool_calls if planned else []:
                    entry = runtime_by_name.get(call.name)
                    if entry is None or usage["tool_calls"] >= 8:
                        continue
                    try:
                        result = await entry.tool.ainvoke(call.arguments)
                        usage["tool_calls"] += 1
                        local_results.append({"tool": call.name, "output": result})
                        store.append_event(
                            run_id,
                            "tool_result",
                            {"task_id": task["task_id"], "tool": call.name, "output": result},
                        )
                    except Exception as exc:
                        local_results.append({"tool": call.name, "error": str(exc)})

                search_result = await provider.search(task["question"])
                usage["search_actions"] += search_result.search_actions
                provider_usage = search_result.usage
                usage["input_tokens"] += int(provider_usage.get("input_tokens", 0) or 0)
                usage["output_tokens"] += int(provider_usage.get("output_tokens", 0) or 0)
                for source in search_result.sources:
                    if usage["sources"] >= int(budget["max_sources"]):
                        break
                    inserted = store.upsert_source(
                        run_id,
                        url=source.url,
                        title=source.title,
                        publisher=source.publisher,
                        snippet=source.snippet,
                        query=task["question"],
                        metadata=source.metadata,
                    )
                    if inserted:
                        usage["sources"] = len((store.get_run(run_id) or {}).get("sources", []))
                summary = search_result.text
                if local_results:
                    summary += "\n\n本地只读工具结果：\n" + json.dumps(local_results, ensure_ascii=False)
                evidence.append({"question": task["question"], "answer": summary})
                store.update_task(task["task_id"], "completed", result_summary=summary)
                store.append_event(
                    run_id,
                    "search_completed",
                    {
                        "task_id": task["task_id"],
                        "round": round_index + 1,
                        "search_actions": search_result.search_actions,
                        "source_count": len(search_result.sources),
                    },
                )
                store.set_status(run_id, "searching", usage=usage)
                yield public_research_snapshot(store.get_run(run_id) or {})

            if _cancelled(run_id):
                return
            store.set_status(run_id, "analyzing", usage=usage)
            yield public_research_snapshot(store.get_run(run_id) or {})
            remaining = int(budget["max_searches"]) - int(usage["search_actions"])
            if round_index + 1 >= int(budget["max_rounds"]) or remaining <= 0:
                break
            gap_finder = getattr(provider, "find_gaps", None)
            if gap_finder is None:
                break
            existing_questions = [
                task["question"] for task in (store.get_run(run_id) or {}).get("tasks", [])
            ]
            gaps = await gap_finder(goal, evidence, existing_questions, remaining)
            added = store.add_tasks(run_id, gaps[:remaining])
            store.append_event(
                run_id,
                "gap_analysis",
                {"round": round_index + 1, "new_questions": gaps[:remaining], "added": added},
            )
            if added == 0:
                break

        sources = (store.get_run(run_id) or {}).get("sources", [])
        coverage_note = ""
        if not sources:
            coverage_note = "未获得可验证 URL。报告必须标记证据不足。"
        elif usage["search_actions"] >= int(budget["max_searches"]):
            coverage_note = "已达到搜索预算。请基于现有证据报告覆盖边界。"

        store.set_status(run_id, "synthesizing", usage=usage)
        yield public_research_snapshot(store.get_run(run_id) or {})
        report = await provider.synthesize(goal, evidence, mode, coverage_note)
        if not sources and "证据不足" not in report:
            report += "\n\n> 证据不足：本次研究未获得可验证的公开来源 URL。"
        store.set_status(run_id, "completed", report=report, usage=usage)
        yield public_research_snapshot(store.get_run(run_id) or {})

    try:
        async with asyncio.timeout(int(budget["timeout_seconds"])):
            async for snapshot in execute():
                yield snapshot
    except TimeoutError:
        current = store.get_run(run_id) or {}
        source_lines = [
            f"- [{item.get('title') or item.get('publisher') or item['canonical_url']}]({item['canonical_url']})"
            for item in current.get("sources", [])[: int(budget["max_sources"])]
        ]
        partial = "研究达到时间预算，已停止继续检索。以下为已获得的证据范围。"
        if source_lines:
            partial += "\n\n### 已收集来源\n\n" + "\n".join(source_lines)
        else:
            partial += "\n\n> 证据不足：尚未获得可验证的公开来源 URL。"
        store.set_status(
            run_id,
            "completed",
            report=partial,
            error="研究达到时间预算，报告覆盖可能不完整",
            usage=usage,
        )
        yield public_research_snapshot(store.get_run(run_id) or {})
    except Exception as exc:
        store.set_status(run_id, "failed", error=str(exc), usage=usage)
        yield public_research_snapshot(store.get_run(run_id) or {})
