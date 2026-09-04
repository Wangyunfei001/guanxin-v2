"""Research provider reliability tests."""

import asyncio
import json

import pytest

import app.research.provider as provider_module


@pytest.mark.asyncio
async def test_provider_call_uses_hard_timeout(monkeypatch):
    monkeypatch.setattr(provider_module, "PROVIDER_CALL_TIMEOUT_SECONDS", 0.01)
    cancelled = asyncio.Event()

    async def hangs_forever():
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    with pytest.raises(provider_module.ProviderTimeoutError, match="Responses API"):
        await provider_module._with_hard_timeout(hangs_forever())

    await asyncio.wait_for(cancelled.wait(), timeout=1)


@pytest.mark.asyncio
async def test_timeout_does_not_wait_for_slow_cancellation(monkeypatch):
    monkeypatch.setattr(provider_module, "PROVIDER_CALL_TIMEOUT_SECONDS", 0.01)
    release = asyncio.Event()
    stopped = asyncio.Event()

    async def slow_cancellation():
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            await release.wait()
        finally:
            stopped.set()

    try:
        with pytest.raises(provider_module.ProviderTimeoutError):
            await asyncio.wait_for(
                provider_module._with_hard_timeout(slow_cancellation()), timeout=1
            )
    finally:
        release.set()
        await asyncio.wait_for(stopped.wait(), timeout=1)


@pytest.mark.asyncio
async def test_research_stream_updates_one_stable_data_part(monkeypatch):
    from app.api import aisdk

    messages = []

    class Store:
        def add_message(self, conversation_id, message):
            messages.append(message)

    async def snapshots(**kwargs):
        for status in ["planning", "searching", "completed"]:
            yield {"run_id": "research-test", "status": status, "report": "完成" if status == "completed" else ""}

    monkeypatch.setattr(aisdk, "get_conversation_store", lambda: Store())
    monkeypatch.setattr(aisdk, "run_research", snapshots)
    output = [event async for event in aisdk._stream_research(
        user_message="研究", conversation_id="conversation-test",
        tenant_id="tenant-a", user_id="admin", mode="deep", catalog=[],
    )]
    events = [json.loads(event[6:]) for event in output if event.startswith("data: {")]
    updates = [event for event in events if event["type"] == "data-research"]
    assert len(updates) == 3
    assert {event["id"] for event in updates} == {"research-test"}
    assert messages[-1].parts[0]["id"] == "research-test"
