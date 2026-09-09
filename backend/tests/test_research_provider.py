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


def test_links_from_model_text_are_not_verified_citations():
    sources = provider_module._sources_from_payload({}, '[来源](https://example.com/a)')
    assert sources[0].metadata["provenance"] == "model_text_unverified"


@pytest.mark.asyncio
async def test_search_keeps_actual_model_usage_and_requires_search():
    class Responses:
        async def create(self, **kwargs):
            assert kwargs["tool_choice"] == "required"
            return {"model": "actual-model", "usage": {"input_tokens": 7, "output_tokens": 3},
                    "output": [{"type": "web_search_call"}, {"type": "message", "content": [
                        {"type": "output_text", "text": "证据", "annotations": [
                            {"url": "https://example.com/a", "title": "来源"}]}]}]}
    class Client:
        responses = Responses()
    result = await provider_module.DeepSeekResearchProvider(client=Client()).search("query")
    assert result.model == "actual-model" and result.usage["input_tokens"] == 7
    assert result.search_actions == 1
    assert result.sources[0].metadata["provenance"] == "provider_annotation"
