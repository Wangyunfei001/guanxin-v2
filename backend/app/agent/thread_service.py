"""Run lifecycle and business projection around the native LangGraph stream."""
from __future__ import annotations

import asyncio
import logging
import uuid

from app.agent.deep_agent import build_deep_agent, checkpoint_config, checkpoint_values, json_value
from app.core.tenant import set_tenant_context
from app.models.agent import ConversationMessage
from app.models.tenant import User
from app.services import agent_run_store as runs
from app.services.conversation_store import get_conversation_store
from app.services.workflow_store import get_workflow_store
from app.workflows.engine import start_workflow
from app.workflows.planner import detect_workflow_intent
from app.workflows.presentation import pending_workflow_part, workflow_public_data

logger = logging.getLogger(__name__)
_tasks: dict[str, asyncio.Task] = {}


def historical_messages(conversation) -> list[dict]:
    return [{"id": m.message_id, "type": "human" if m.role == "user" else "ai",
             "content": m.content, "additional_kwargs": {"legacy_parts": m.parts}}
            for m in conversation.messages if m.role in {"user", "assistant"}]


async def thread_values(conversation) -> dict:
    values = await checkpoint_values(conversation.conversation_id)
    checkpoint_messages = values.get("messages", [])
    ids = {m.get("id") for m in checkpoint_messages}
    # Checkpoint order includes tool replies between AI messages. Do not merge
    # via the compatibility transcript, which intentionally omits tool replies.
    old = historical_messages(conversation)
    prefix, suffix = [], []
    encountered_checkpoint = False
    for message in old:
        if message["id"] in ids:
            encountered_checkpoint = True
        else:
            (suffix if encountered_checkpoint else prefix).append(message)
    values["messages"] = prefix + checkpoint_messages + suffix
    active = get_workflow_store().get_active_for_conversation(
        conversation.conversation_id, conversation.tenant_id, conversation.user_id)
    if active:
        values["workflow"] = workflow_public_data(active)
    run = runs.latest_run(conversation.conversation_id)
    values["run_status"] = run["status"] if run else "idle"
    values["run_error"] = run["error"] if run else ""
    from app.research.ledger import snapshot
    values["research_review"] = snapshot(conversation.conversation_id)
    return values


def save_workflow(run: dict) -> None:
    get_conversation_store().upsert_workflow_message(
        run["conversation_id"], run["run_id"], workflow_public_data(run), pending_workflow_part(run))


def launch_run(run: dict, user: User, message: dict | None, mode: str) -> None:
    task = asyncio.create_task(_execute(run, user, message, mode), name=f"agent-{run['run_id']}")
    _tasks[run["conversation_id"]] = task
    def done(completed):
        if _tasks.get(run["conversation_id"]) is completed:
            _tasks.pop(run["conversation_id"], None)
        if not completed.cancelled() and completed.exception():
            logger.error("Agent task cleanup failed", exc_info=completed.exception())
    task.add_done_callback(done)


async def cancel_run(conversation_id: str) -> None:
    task = _tasks.get(conversation_id)
    if task:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def close_runs() -> None:
    tasks = list(_tasks.values())
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    _tasks.clear()


async def _execute(run: dict, user: User, message: dict | None, mode: str) -> None:
    cid = run["conversation_id"]
    store = get_conversation_store()
    set_tenant_context(user.tenant_id, user.user_id, user.role)
    runs.append_event(run, runs.protocol_event("lifecycle", {"event": "running"}))
    try:
        async with asyncio.timeout(480):
            conversation = store.get_conversation_for_user(cid, user.tenant_id, user.user_id)
            if conversation is None:
                raise ValueError("会话已删除")
            if message is not None:
                store.add_message(cid, ConversationMessage(message_id=message["id"], role="user", content=message["content"]))
            previous = await checkpoint_values(cid)
            intent = detect_workflow_intent(message["content"]) if message else ""
            if intent:
                workflow = await start_workflow(user_message=message["content"], intent=intent,
                    tenant_id=user.tenant_id, user_id=user.user_id, user_role=user.role,
                    conversation_id=cid, agent_id="default")
                save_workflow(workflow)
            else:
                agent = await build_deep_agent(cid, user, mode)
                graph_input = None
                if message is not None:
                    # Import only text for old turns; never replay historical tool calls.
                    history = [] if previous.get("messages") else [
                        {"id": m.message_id, "role": m.role, "content": m.content}
                        for m in conversation.messages if m.role in {"user", "assistant"}]
                    graph_input = {"messages": [*history, {**message, "type": "human"}]}
                else:
                    # Cancellation can happen after accepting the human message
                    # but before LangGraph writes its input checkpoint.
                    checkpoint_ids = {m.get("id") for m in previous.get("messages", [])}
                    missing = [{"id": m.message_id, "role": m.role, "content": m.content}
                        for m in conversation.messages if m.role in {"user", "assistant"}
                        and m.message_id not in checkpoint_ids]
                    if missing:
                        graph_input = {"messages": missing}
                async with await agent.astream_events(graph_input, checkpoint_config(cid), version="v3") as stream:
                    async for event in stream:
                        # Native event semantics are retained; only JSON serialization,
                        # durable sequence ids and business presentation live here.
                        event = json_value(event)
                        if event.get("method") == "messages":
                            # Python emits (content event, LangGraph metadata);
                            # JS protocol v2 puts the event directly in data.
                            payload = event["params"]["data"]
                            if isinstance(payload, list) and len(payload) == 2:
                                content, metadata = payload
                                if not isinstance(content, dict) or "event" not in content:
                                    continue  # complete non-streamed messages arrive in values
                                event["params"]["data"] = content
                                event["params"]["node"] = metadata.get("langgraph_node", "model")
                        if event.get("method") == "lifecycle" and not event["params"]["namespace"]:
                            continue  # our task terminal follows checkpoint + business persistence
                        if event.get("method") == "values" and not event["params"]["namespace"]:
                            event["params"]["data"]["run_status"] = "running"
                        runs.append_event(run, event)
                await _persist_transcript(cid, user)
            fresh = store.get_conversation_for_user(cid, user.tenant_id, user.user_id)
            values = await thread_values(fresh)
            status = "waiting_approval" if values.get("workflow") else "completed"
            values["run_status"] = status
            runs.append_event(run, runs.protocol_event("values", values))
            runs.finish_run(run, status)
    except asyncio.CancelledError:
        try:
            await _persist_transcript(cid, user)
        finally:
            await _finish_failed_run(run, user, "cancelled")
    except Exception as exc:
        logger.exception("Agent run %s failed", run["run_id"])
        try:
            await _persist_transcript(cid, user)
        finally:
            await _finish_failed_run(run, user, "failed", str(exc) or type(exc).__name__)


async def _finish_failed_run(run: dict, user: User, status: str, error: str = "") -> None:
    try:
        conversation = get_conversation_store().get_conversation_for_user(
            run["conversation_id"], user.tenant_id, user.user_id)
        if conversation:
            values = await thread_values(conversation)
            values.update(run_status=status, run_error=error)
            runs.append_event(run, runs.protocol_event("values", values))
    finally:
        runs.finish_run(run, status, error)


async def _persist_transcript(cid: str, user: User) -> None:
    """A compatibility transcript for existing history/export, not execution state."""
    store = get_conversation_store()
    conversation = store.get_conversation_for_user(cid, user.tenant_id, user.user_id)
    if not conversation:
        return
    known = {m.message_id for m in conversation.messages}
    for message in (await checkpoint_values(cid)).get("messages", []):
        if message.get("type") != "ai" or not message.get("id") or message["id"] in known:
            continue
        content = message.get("content", "")
        if isinstance(content, list):
            content = "\n".join(str(b.get("text", "")) for b in content if isinstance(b, dict) and b.get("type") == "text")
        store.add_message(cid, ConversationMessage(message_id=message["id"], role="assistant",
            content=content, tool_calls=message.get("tool_calls", [])))
        known.add(message["id"])
