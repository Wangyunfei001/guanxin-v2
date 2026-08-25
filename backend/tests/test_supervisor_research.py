"""Unified Supervisor, Tool Catalog and persistent Research tests."""

from __future__ import annotations

import uuid

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from app.agent.supervisor import decide_route, deterministic_route
from app.agent.executor import _execute_unified
from app.agent.tool_catalog import CatalogEntry, ToolSpec, build_tool_catalog
from app.models.agent import AgentConfig
from app.models.tenant import User
from app.services.conversation_store import get_conversation_store
from app.research.engine import run_research
from app.research.models import (
    ResearchPlan,
    ResearchQuestionPlan,
    ResearchSource,
    SearchResult,
)
from app.services.research_store import canonicalize_url, get_research_store


class WeatherArgs(BaseModel):
    city: str


async def _weather(city: str) -> dict:
    return {"city": city, "temperature": 21}


def _weather_entry() -> CatalogEntry:
    tool = StructuredTool.from_function(
        coroutine=_weather,
        name="mcp__weather__get_weather",
        description="查询模拟天气",
        args_schema=WeatherArgs,
    )
    return CatalogEntry(
        spec=ToolSpec(
            name=tool.name,
            display_name="模拟天气",
            description="查询天气模拟数据",
            input_schema=WeatherArgs.model_json_schema(),
            source_type="mcp",
            source_name="weather",
            effect="read",
            approval_required=False,
        ),
        tool=tool,
    )


def test_weather_route_uses_structured_mcp_tool() -> None:
    decision = deterministic_route("北京市今天天气怎么样？", [_weather_entry()])
    assert decision is not None
    assert decision.route == "tool_loop"
    assert decision.candidate_tools == ["mcp__weather__get_weather"]
    assert _weather_entry().spec.input_schema["properties"]["city"]["type"] == "string"


def test_sequence_words_no_longer_force_workflow() -> None:
    decision = deterministic_route("介绍功能，然后说明优点", [])
    assert decision is None


@pytest.mark.asyncio
async def test_explicit_deep_research_phrase_is_not_downgraded() -> None:
    config = AgentConfig(agent_id="default", tenant_id="route", name="Route")
    entry = CatalogEntry(
        spec=ToolSpec(
            name="deep_research",
            display_name="Deep Research",
            description="多来源研究",
            source_type="provider",
            source_name="deepseek",
            effect="read",
            approval_required=False,
        )
    )
    decision = await decide_route(
        "请深入研究这个行业",
        config,
        [entry],
        research_mode="auto",
    )
    assert decision.route == "research"
    assert decision.research_mode == "deep"


class FakeToolLoopLlm:
    def __init__(self) -> None:
        self.calls = 0
        self.tool_choices: list[str] = []

    def bind_tools(self, tools, tool_choice="auto"):
        self.tool_choices.append(tool_choice)
        return self

    async def ainvoke(self, messages):
        self.calls += 1
        if self.calls == 1:
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "mcp__weather__get_weather",
                        "args": {"city": "北京"},
                        "id": "call-weather-stable",
                        "type": "tool_call",
                    }
                ],
            )
        return AIMessage(content="北京模拟天气为 21°C。")


@pytest.mark.asyncio
async def test_tool_loop_persists_stable_structured_call() -> None:
    suffix = uuid.uuid4().hex
    conversation = get_conversation_store().create_conversation(
        f"tenant-{suffix}",
        f"user-{suffix}",
        "default",
    )
    llm = FakeToolLoopLlm()
    decision = deterministic_route("北京天气", [_weather_entry()])
    assert decision is not None
    events = []
    async for event in _execute_unified(
        user_message="北京天气",
        conversation_id=conversation.conversation_id,
        tenant_id=conversation.tenant_id,
        system_prompt="测试",
        llm=llm,
        catalog=[_weather_entry()],
        decision=decision,
    ):
        events.append(event)
    assert llm.tool_choices[0] == "mcp__weather__get_weather"
    assert any('"tool_call_id": "call-weather-stable"' in event for event in events)
    assert any('\\"city\\": \\"北京\\"' in event for event in events)

    restored = get_conversation_store().get_conversation(
        conversation.conversation_id,
        conversation.tenant_id,
    )
    assert restored is not None
    assistant = restored.messages[-1]
    tool_part = next(part for part in assistant.parts if part["type"].startswith("tool-"))
    assert tool_part["toolCallId"] == "call-weather-stable"
    assert tool_part["input"] == {"city": "北京"}


@pytest.mark.asyncio
async def test_skill_catalog_preserves_array_schema() -> None:
    config = AgentConfig(
        agent_id="default",
        tenant_id="catalog-test",
        name="Catalog",
        enabled_tools=[],
        enabled_skills=["data_analysis"],
    )
    entries = await build_tool_catalog(
        config,
        tenant_id=config.tenant_id,
        user_id="user",
        user_role="user",
        ensure_mcp=False,
    )
    analysis = next(item for item in entries if item.spec.name == "skill__data_analysis")
    assert analysis.spec.input_schema["properties"]["data"]["type"] == "array"
    assert analysis.tool is not None


class FakeResearchProvider:
    def __init__(self) -> None:
        self.gap_calls = 0

    async def plan(self, goal, mode, tool_specs, max_questions):
        return ResearchPlan(
            summary="测试计划",
            questions=[ResearchQuestionPlan(question=goal)],
        )

    async def search(self, query):
        return SearchResult(
            text="测试证据 [来源](https://example.com/report?utm_source=test)",
            sources=[
                ResearchSource(url="https://example.com/report?utm_source=test", title="来源 A"),
                ResearchSource(url="https://example.com/report", title="来源 A 重复"),
            ],
            search_actions=1,
            usage={"input_tokens": 5, "output_tokens": 7},
        )

    async def synthesize(self, goal, evidence, mode, coverage_note=""):
        return "结论来自 [来源](https://example.com/report)。"

    async def find_gaps(self, goal, evidence, existing_questions, remaining_searches):
        self.gap_calls += 1
        return ["补充验证问题"] if self.gap_calls == 1 else []


@pytest.mark.asyncio
async def test_research_persists_and_deduplicates_sources() -> None:
    suffix = uuid.uuid4().hex
    tenant_id = f"tenant-{suffix}"
    user_id = f"user-{suffix}"
    conversation = get_conversation_store().create_conversation(
        tenant_id,
        user_id,
        "default",
    )
    snapshots = []
    async for snapshot in run_research(
        tenant_id=tenant_id,
        user_id=user_id,
        conversation_id=conversation.conversation_id,
        goal="测试公开信息",
        mode="quick",
        catalog=[],
        provider=FakeResearchProvider(),
    ):
        snapshots.append(snapshot)
    final = snapshots[-1]
    assert final["status"] == "completed"
    assert len(final["sources"]) == 1
    assert final["usage"]["search_actions"] == 2
    assert len(final["tasks"]) == 2
    assert "https://example.com/report" in final["report"]
    assert canonicalize_url("https://example.com/report?utm_source=test") == "https://example.com/report"

    store = get_research_store()
    assert store.get_run(final["run_id"], "other-tenant", user_id) is None


@pytest.mark.asyncio
async def test_mcp_connect_enables_only_current_tenant(monkeypatch) -> None:
    from app.api import mcp as mcp_api
    from app.models.agent import get_agent_config_store

    class FakeMcpClient:
        async def connect(self, **kwargs):
            return {
                "server_name": kwargs["server_name"],
                "status": "connected",
                "tools": [
                    {
                        "name": "get_weather",
                        "description": "模拟天气",
                        "input_schema": {
                            "type": "object",
                            "properties": {"city": {"type": "string"}},
                            "required": ["city"],
                        },
                        "annotations": {"readOnlyHint": True},
                    }
                ],
            }

    monkeypatch.setattr(mcp_api, "get_mcp_client", lambda: FakeMcpClient())
    suffix = uuid.uuid4().hex
    tenant_id = f"tenant-{suffix}"
    other_tenant = f"other-{suffix}"
    user = User(
        user_id=f"admin-{suffix}",
        username="admin",
        password_hash="",
        tenant_id=tenant_id,
        tenant_name="测试租户",
        role="admin",
    )
    response = await mcp_api.connect_server(
        mcp_api.ConnectRequest(server_name="weather"),
        user,
    )
    assert response["data"]["agent_enabled"] is True
    assert response["data"]["tools"][0]["policy"]["effect"] == "read"
    store = get_agent_config_store()
    assert "weather" in store.get_or_create_default(tenant_id).mcp_servers
    assert "weather" not in store.get_or_create_default(other_tenant).mcp_servers
