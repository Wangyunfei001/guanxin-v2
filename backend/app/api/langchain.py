"""Authenticated endpoints for @langchain/react's HttpAgentServerAdapter."""
from __future__ import annotations

import asyncio
import json
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.agent.deep_agent import checkpoint_values
from app.agent.thread_service import cancel_run, launch_run, save_workflow, thread_values
from app.core.deps import get_current_user
from app.core.responses import success
from app.models.tenant import User
from app.services import agent_run_store as runs
from app.services.conversation_store import get_conversation_store
from app.services.workflow_store import WorkflowConflictError, get_workflow_store
from app.workflows.engine import resume_workflow
from app.workflows.presentation import workflow_public_data
from app.workflows.catalog import catalog_by_name
from app.models.agent import get_agent_config_store

router = APIRouter(prefix="/agent", tags=["LangChain"])


def file_text(file: dict) -> str:
    content = file.get("content", "")
    return content if isinstance(content, str) else "\n".join(content)


def owned_thread(cid: str, user: User):
    conversation = get_conversation_store().get_conversation_for_user(cid, user.tenant_id, user.user_id)
    if conversation is None:
        raise HTTPException(404, "对话未找到")
    return conversation


@router.get("/threads/{cid}/state")
async def state(cid: str, user: User = Depends(get_current_user)):
    values = await thread_values(owned_thread(cid, user))
    result = {"values": values, "tasks": [], "checkpoint": None, "metadata": {}}
    # An empty next proves idle to the official SDK and disables its SSE pump.
    # While our background worker runs, omit next rather than invent graph nodes.
    if values["run_status"] != "running":
        result["next"] = []
    return result


@router.post("/threads/{cid}/commands")
async def command(cid: str, request: Request, user: User = Depends(get_current_user)):
    owned_thread(cid, user)
    body = await request.json()
    if not isinstance(body, dict) or not isinstance(body.get("params", {}), dict):
        raise HTTPException(422, "命令格式不合法")
    method, params = body.get("method"), body.get("params") or {}
    if method != "run.start":
        return {"type": "error", "id": body.get("id"), "error": "not_supported",
                "message": "当前使用业务工作流审批接口；此命令尚未启用。"}
    # All model/tool/identity/checkpoint settings come from the server, never
    # from protocol config, assistant_id or arbitrary client state updates.
    input_data = params.get("input")
    message = None
    mode = "auto"
    if input_data is not None:
        if not isinstance(input_data, dict) or set(input_data) - {"messages", "research_mode"}:
            raise HTTPException(422, "只允许提交用户消息和研究模式")
        mode = input_data.get("research_mode", "auto")
        messages = input_data.get("messages")
        if mode not in {"auto", "quick", "deep"} or not isinstance(messages, list) or len(messages) != 1:
            raise HTTPException(422, "每次只能提交一条用户消息，研究模式必须为 auto/quick/deep")
        raw = messages[0]
        if not isinstance(raw, dict) or raw.get("type", raw.get("role")) not in {"human", "user"}:
            raise HTTPException(422, "只允许用户消息")
        content = raw.get("content")
        if not isinstance(content, str) or not content.strip() or len(content) > 100_000:
            raise HTTPException(422, "消息必须为非空文本，且不超过 100000 字符")
        message_id = raw.get("id") or str(uuid.uuid4())
        if not isinstance(message_id, str) or len(message_id) > 128:
            raise HTTPException(422, "消息 ID 不合法")
        message = {"id": message_id, "content": content}
    if get_workflow_store().get_active_for_conversation(cid, user.tenant_id, user.user_id):
        raise HTTPException(409, "请先处理或取消当前工作流")
    if message is None:
        previous = runs.latest_run(cid)
        if not previous or previous["status"] not in {"failed", "cancelled", "interrupted"}:
            raise HTTPException(409, "没有可继续的中断任务")
    try:
        run, created = runs.admit_run(cid, message["id"] if message else f"resume:{uuid.uuid4()}")
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    if created:
        launch_run(run, user, message, mode)
    return {"type": "success", "id": body.get("id"), "result": {"run_id": run["run_id"]}}


@router.post("/threads/{cid}/history")
async def history(cid: str, user: User = Depends(get_current_user)):
    owned_thread(cid, user)
    # The SDK may request branching history after submit. This migration
    # exposes latest-state hydration only, not checkpoint branching controls.
    return []


@router.post("/threads/{cid}/stream/events")
async def events(cid: str, request: Request, user: User = Depends(get_current_user)):
    owned_thread(cid, user)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(422, "订阅格式不合法")
    since = body.get("since", 0)
    if not isinstance(since, int) or since < 0:
        raise HTTPException(422, "since 必须为非负整数")
    channels = body.get("channels")

    async def stream():
        cursor, idle = since, 0
        yield ": connected\n\n"
        while not await request.is_disconnected():
            # Authentication was established by Depends. Ownership is checked
            # again so deleting a thread also terminates its subscriptions.
            if not get_conversation_store().get_conversation_for_user(cid, user.tenant_id, user.user_id):
                return
            batch = runs.read_events(cid, cursor)
            for event in batch:
                cursor = event["seq"]
                if channels and event["method"] not in channels:
                    continue
                yield f"id: {event['event_id']}\nevent: {event['method']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
            if batch:
                idle = 0
                continue
            idle += 1
            if idle % 20 == 0:
                yield ": heartbeat\n\n"
            await asyncio.sleep(.25)

    return StreamingResponse(stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no",
                 "Content-Encoding": "identity"})


@router.post("/threads/{cid}/cancel")
async def cancel(cid: str, user: User = Depends(get_current_user)):
    owned_thread(cid, user)
    await cancel_run(cid)
    return success({"cancelled": True})


@router.get("/threads/{cid}/files")
async def files(cid: str, user: User = Depends(get_current_user)):
    owned_thread(cid, user)
    values = await checkpoint_values(cid)
    return success([{"path": path, "size": len(file_text(file).encode())}
                    for path, file in values.get("files", {}).items()])


@router.get("/threads/{cid}/files/content")
async def file_content(cid: str, path: str, user: User = Depends(get_current_user)):
    owned_thread(cid, user)
    file = (await checkpoint_values(cid)).get("files", {}).get(path)
    if file is None:
        raise HTTPException(404, "文件未找到")
    return PlainTextResponse(file_text(file), headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(path.rsplit('/', 1)[-1], safe='')}"})


class WorkflowResponse(BaseModel):
    interrupt_id: str
    accepted: bool
    values: dict = Field(default_factory=dict)


@router.post("/workflows/{run_id}/respond")
async def respond_workflow(run_id: str, body: WorkflowResponse, user: User = Depends(get_current_user)):
    run = get_workflow_store().get_run(run_id, user.tenant_id, user.user_id)
    if run is None:
        raise HTTPException(404, "工作流未找到")
    pending = get_workflow_store().get_interrupt(body.interrupt_id)
    if not pending or pending["run_id"] != run_id:
        raise HTTPException(404, "审批未找到")
    if body.accepted and pending["status"] == "pending":
        config = get_agent_config_store().get_config(user.tenant_id, run["agent_id"])
        allowed = catalog_by_name(config, user.role) if config else {}
        step = next((s for s in run["steps"] if s["step_id"] == pending["step_id"]), None)
        if step is None or step["tool_name"] not in allowed:
            raise HTTPException(403, "工具已禁用或当前用户无权执行")
    try:
        updated = await resume_workflow(interrupt_id=body.interrupt_id, accepted=body.accepted,
            values=body.values, tenant_id=user.tenant_id, user_id=user.user_id, user_role=user.role)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except (ValueError, LookupError, WorkflowConflictError) as exc:
        raise HTTPException(409, str(exc)) from exc
    save_workflow(updated)
    return success(workflow_public_data(updated))
