"""Persistent workflow planning, recovery and API acceptance tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models.agent import AgentConfig, get_agent_config_store
from app.services.conversation_store import get_conversation_store
from app.services.workflow_store import WorkflowConflictError, get_workflow_store
from app.workflows.catalog import build_tool_catalog
from app.workflows.models import WorkflowPlan
from app.workflows.planner import validate_and_normalize_plan


def _enable_create_user() -> AgentConfig:
    store = get_agent_config_store()
    original = store.get_or_create_default("tenant-a")
    updated = AgentConfig(**{
        **original.__dict__,
        "enabled_skills": sorted(set(original.enabled_skills + ["create_user"])),
    })
    store.save_config(updated)
    return original


def test_plan_rejects_more_than_sixteen_steps():
    with pytest.raises(ValidationError):
        WorkflowPlan.model_validate({
            "goal": "too long",
            "steps": [
                {"step_id": f"step_{index}", "title": "x", "tool_name": "kb_retrieval"}
                for index in range(17)
            ],
        })


def test_plan_validates_tool_allowlist_and_forward_references():
    config = AgentConfig(
        agent_id="default",
        tenant_id="tenant-plan",
        name="planner",
        enabled_tools=["kb_retrieval"],
    )
    catalog = build_tool_catalog(config, "user")
    valid = WorkflowPlan.model_validate({
        "goal": "search twice",
        "steps": [
            {
                "step_id": "step_1",
                "title": "first",
                "tool_name": "kb_retrieval",
                "arguments": {"query": "hello"},
            },
            {
                "step_id": "step_2",
                "title": "second",
                "tool_name": "kb_retrieval",
                "arguments": {"query": "$steps.step_1.output.sources.0.content"},
            },
        ],
    })
    normalized, persisted = validate_and_normalize_plan(valid, catalog)
    assert normalized.steps[1].arguments["query"].startswith("$steps.step_1")
    assert persisted[0]["risk"] == "read"

    invalid = WorkflowPlan.model_validate({
        "goal": "bad",
        "steps": [{
            "step_id": "step_1",
            "title": "bad",
            "tool_name": "kb_retrieval",
            "arguments": {"query": "$steps.step_2.output"},
        }],
    })
    with pytest.raises(RuntimeError, match="非法前序引用"):
        validate_and_normalize_plan(invalid, catalog)


def test_store_allows_only_one_active_run_per_conversation():
    conv = get_conversation_store().create_conversation(
        "tenant-a", "admin-001", "default", "unique workflow"
    )
    store = get_workflow_store()
    kwargs = {
        "tenant_id": "tenant-a",
        "user_id": "admin-001",
        "conversation_id": conv.conversation_id,
        "agent_id": "default",
        "goal": "test",
        "summary": "",
        "plan": {"goal": "test", "steps": []},
        "steps": [{
            "step_id": "step_1",
            "title": "search",
            "tool_name": "kb_retrieval",
            "tool_category": "knowledge",
            "arguments": {"query": "q"},
            "risk": "read",
        }],
    }
    first = store.create_run(**kwargs)
    with pytest.raises(WorkflowConflictError):
        store.create_run(**kwargs)
    store.cancel(first["run_id"])
    assert store.create_run(**kwargs)["status"] == "running"


def test_workflow_resumes_once_and_rejects_duplicate_approval(test_client, admin_headers, monkeypatch):
    from tests.test_langchain import new_thread, submit, settled
    original = _enable_create_user()
    calls = 0
    async def fake_execute(tool, arguments, context):
        nonlocal calls
        calls += 1
        return {"success": True, "output": {"username": arguments["username"]}}
    monkeypatch.setattr("app.workflows.engine.execute_tool", fake_execute)
    try:
        cid = new_thread(test_client, admin_headers)
        assert submit(test_client, admin_headers, cid, "创建一个用户").status_code == 200
        state = settled(test_client, admin_headers, cid)
        run = state["workflow"]
        assert run["status"] == "waiting_input"
        url = f"/api/agent/workflows/{run['run_id']}/respond"
        response = test_client.post(url, headers=admin_headers, json={
            "interrupt_id": run["pending_interrupt"]["interrupt_id"], "accepted": True,
            "values": {"username": "once", "email": "once@example.com", "role": "user"}})
        assert response.status_code == 200
        run = response.json()["data"]
        assert run["status"] == "waiting_approval"
        body = {"interrupt_id": run["pending_interrupt"]["interrupt_id"], "accepted": True, "values": {}}
        first = test_client.post(url, headers=admin_headers, json=body)
        second = test_client.post(url, headers=admin_headers, json=body)
        assert first.json()["data"]["status"] == second.json()["data"]["status"] == "completed"
        assert calls == 1
        history = get_conversation_store().get_conversation(cid, "tenant-a")
        messages = [m for m in history.messages if any(p.get("type") == "data-workflow" for p in m.parts)]
        assert len(messages) == 1
        assert messages[0].message_id == f"workflow-msg-{run['run_id']}"
        parts = messages[0].parts
        assert len([p for p in parts if p.get("type") == "data-workflow"]) == 1
        assert not any(p.get("type") == "tool-workflow_control" for p in parts)
        assert not any(p.get("type") == "text" for p in parts)
    finally:
        get_agent_config_store().save_config(original)


def test_workflow_rejection_updates_the_canonical_message(test_client, admin_headers):
    from tests.test_langchain import new_thread, submit, settled
    original = _enable_create_user()
    try:
        cid = new_thread(test_client, admin_headers)
        submit(test_client, admin_headers, cid, "创建一个用户")
        run = settled(test_client, admin_headers, cid)["workflow"]
        response = test_client.post(f"/api/agent/workflows/{run['run_id']}/respond", headers=admin_headers,
            json={"interrupt_id": run["pending_interrupt"]["interrupt_id"], "accepted": False, "values": {}})
        assert response.status_code == 200 and response.json()["data"]["status"] == "cancelled"
        history = get_conversation_store().get_conversation(cid, "tenant-a")
        messages = [m for m in history.messages if m.message_id == f"workflow-msg-{run['run_id']}"]
        assert len(messages) == 1
        assert messages[0].parts[0]["data"]["status"] == "cancelled"
        assert not any(p.get("type") == "tool-workflow_control" for p in messages[0].parts)
    finally:
        get_agent_config_store().save_config(original)


def test_recover_inflight_risk_step_becomes_uncertain():
    original = _enable_create_user()
    try:
        conv = get_conversation_store().create_conversation(
            "tenant-a", "admin-001", "default", "uncertain"
        )
        store = get_workflow_store()
        run = store.create_run(
            tenant_id="tenant-a",
            user_id="admin-001",
            conversation_id=conv.conversation_id,
            agent_id="default",
            goal="write",
            summary="",
            plan={"goal": "write"},
            steps=[{
                "step_id": "step_1",
                "title": "create",
                "tool_name": "skill__create_user",
                "tool_category": "skill",
                "arguments": {},
                "risk": "write",
            }],
        )
        store.begin_execution(run["run_id"], run["steps"][0]["db_step_id"])
        assert store.recover_inflight() >= 1
        recovered = store.get_run(run["run_id"])
        assert recovered["status"] == "uncertain"
        assert recovered["interrupts"][-1]["kind"] == "recovery"
    finally:
        get_agent_config_store().save_config(original)


def test_checkpoint_resume_after_process_restart(tmp_path):
    database = tmp_path / "business.db"
    checkpoints = tmp_path / "checkpoints.db"
    handoff = tmp_path / "handoff.json"
    environment = {
        **os.environ,
        "APP_ENV": "test",
        "DATABASE_PATH": str(database),
        "CHECKPOINT_DATABASE_PATH": str(checkpoints),
        "OPENAI_API_KEY": "",
    }
    phase_one = textwrap.dedent(f"""
        import asyncio, json
        from pathlib import Path
        from app.core.sqlite import initialize_database
        from app.core.checkpoints import initialize_checkpointer, close_checkpointer
        from app.models.agent import AgentConfig, get_agent_config_store
        from app.services.conversation_store import get_conversation_store
        from app.workflows.engine import start_workflow, resume_workflow

        async def main():
            initialize_database(); await initialize_checkpointer()
            get_agent_config_store().save_config(AgentConfig(
                agent_id='default', tenant_id='tenant-restart', name='test',
                enabled_tools=['kb_retrieval'], enabled_skills=['create_user'],
            ))
            conv = get_conversation_store().create_conversation(
                'tenant-restart', 'admin-restart', 'default'
            )
            run = await start_workflow(
                user_message='创建一个用户', intent='single_create',
                tenant_id='tenant-restart', user_id='admin-restart',
                user_role='admin', conversation_id=conv.conversation_id,
                agent_id='default',
            )
            run = await resume_workflow(
                interrupt_id=run['interrupts'][-1]['interrupt_id'],
                accepted=True,
                values={{'username':'restart','email':'restart@example.com','role':'user'}},
                tenant_id='tenant-restart', user_id='admin-restart', user_role='admin',
            )
            Path({str(handoff)!r}).write_text(json.dumps({{
                'run_id': run['run_id'],
                'interrupt_id': run['interrupts'][-1]['interrupt_id'],
            }}))
            await close_checkpointer()
        asyncio.run(main())
    """)
    first = subprocess.run(
        [sys.executable, "-c", phase_one],
        cwd=str(Path(__file__).parent.parent),
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert first.returncode == 0, first.stderr

    phase_two = textwrap.dedent(f"""
        import asyncio, json
        from pathlib import Path
        from app.core.checkpoints import initialize_checkpointer, close_checkpointer
        from app.workflows.engine import resume_workflow

        async def main():
            await initialize_checkpointer()
            handoff = json.loads(Path({str(handoff)!r}).read_text())
            run = await resume_workflow(
                interrupt_id=handoff['interrupt_id'], accepted=False, values={{}},
                tenant_id='tenant-restart', user_id='admin-restart', user_role='admin',
            )
            print(run['status'])
            await close_checkpointer()
        asyncio.run(main())
    """)
    second = subprocess.run(
        [sys.executable, "-c", phase_two],
        cwd=str(Path(__file__).parent.parent),
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert second.returncode == 0, second.stderr
    assert second.stdout.strip() == "cancelled"


def test_workflow_api_rbac_history_and_conversation_lock(test_client, admin_headers, demo_headers):
    from tests.test_langchain import new_thread, submit, settled
    original = _enable_create_user()
    try:
        cid = new_thread(test_client, admin_headers)
        submit(test_client, admin_headers, cid, "创建一个用户")
        run = settled(test_client, admin_headers, cid)["workflow"]
        url = f"/api/agent/workflows/{run['run_id']}"
        assert test_client.get(url, headers=demo_headers).status_code == 404
        body = {"interrupt_id": run["pending_interrupt"]["interrupt_id"], "accepted": True, "values": {}}
        assert test_client.post(url + "/respond", headers=demo_headers, json=body).status_code == 404
        assert submit(test_client, admin_headers, cid, "另一项任务").status_code == 409
        # Grants are rechecked before approving an existing interrupt.
        disabled = AgentConfig(**{**original.__dict__, "enabled_skills": []})
        get_agent_config_store().save_config(disabled)
        assert test_client.post(url + "/respond", headers=admin_headers, json=body).status_code == 403
        cancelled = test_client.post(url + "/cancel", headers=admin_headers)
        assert cancelled.json()["data"]["status"] == "cancelled"
        history = test_client.get(f"/api/agent/conversations/{cid}", headers=admin_headers).json()["data"]
        parts = [p for m in history["messages"] for p in m["parts"]]
        assert any(p.get("type") == "data-workflow" and p["data"]["status"] == "cancelled" for p in parts)
        assert not any(p.get("type") == "tool-workflow_control" for p in parts)
    finally:
        get_agent_config_store().save_config(original)
