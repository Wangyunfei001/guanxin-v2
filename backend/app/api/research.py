"""Authenticated Deep Research lifecycle API."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from app.agent.tool_catalog import build_tool_catalog
from app.core.deps import get_current_user
from app.core.responses import success
from app.models.agent import get_agent_config_store
from app.models.tenant import User
from app.research.engine import public_research_snapshot, run_research
from app.services.research_store import get_research_store


router = APIRouter(prefix="/agent/research", tags=["Research"])
_background_tasks: set[asyncio.Task] = set()


@router.get("/{run_id}")
async def get_research_run(
    run_id: str,
    user: User = Depends(get_current_user),
):
    run = get_research_store().get_run(run_id, user.tenant_id, user.user_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Research 运行不存在")
    return success(public_research_snapshot(run))


@router.post("/{run_id}/cancel")
async def cancel_research_run(
    run_id: str,
    user: User = Depends(get_current_user),
):
    run = get_research_store().cancel(run_id, user.tenant_id, user.user_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Research 运行不存在")
    return success(public_research_snapshot(run))


async def _resume_in_background(run: dict, user: User) -> None:
    config = get_agent_config_store().get_or_create_default(user.tenant_id)
    catalog = await build_tool_catalog(
        config,
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        user_role=user.role,
    )
    async for _ in run_research(
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        conversation_id=run["conversation_id"],
        goal=run["goal"],
        mode=run["mode"],
        catalog=catalog,
        resume_run_id=run["run_id"],
    ):
        pass


@router.post("/{run_id}/resume")
async def resume_research_run(
    run_id: str,
    user: User = Depends(get_current_user),
):
    store = get_research_store()
    run = store.get_run(run_id, user.tenant_id, user.user_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Research 运行不存在")
    if run["status"] != "interrupted":
        raise HTTPException(status_code=409, detail="只有 interrupted 运行可以恢复")
    store.set_status(run_id, "planning", error="")
    task = asyncio.create_task(_resume_in_background(run, user))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return success(public_research_snapshot(store.get_run(run_id) or run))
