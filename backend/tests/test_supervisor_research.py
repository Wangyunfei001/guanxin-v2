"""Tool Catalog and persistent Research tests."""

from __future__ import annotations

import uuid

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from app.agent.tool_catalog import CatalogEntry, ToolSpec, build_tool_catalog
from app.models.agent import AgentConfig
from app.models.tenant import User
from app.services.conversation_store import get_conversation_store

from app.services.research_store import canonicalize_url, get_research_store


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


def test_archived_research_sources_remain_readable_and_deduplicated():
    store = get_research_store()
    conversation = get_conversation_store().create_conversation("archive", "user", "default")
    run = store.create_run(tenant_id="archive", user_id="user", conversation_id=conversation.conversation_id,
        mode="quick", goal="历史研究", budget={})
    store.upsert_source(run["run_id"], url="https://example.com/report?utm_source=test")
    store.upsert_source(run["run_id"], url="https://example.com/report")
    store.set_status(run["run_id"], "completed", report="历史报告")
    saved = store.get_run(run["run_id"], "archive", "user")
    assert len(saved["sources"]) == 1 and saved["report"] == "历史报告"
    assert store.get_run(run["run_id"], "other", "user") is None


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
