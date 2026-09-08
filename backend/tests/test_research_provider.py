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


def test_native_event_log_replays_stable_ids(test_client, admin_headers):
    from tests.test_langchain import new_thread
    from app.services import agent_run_store as runs
    cid = new_thread(test_client, admin_headers)
    run, _ = runs.admit_run(cid, "replay-test")
    for text in ["first", "second"]:
        runs.append_event(run, runs.protocol_event("values", {"messages": [], "report": text}))
    runs.finish_run(run, "completed")
    first = runs.read_events(cid, 0)
    assert first == runs.read_events(cid, 0)
    assert runs.read_events(cid, first[0]["seq"]) == first[1:]
