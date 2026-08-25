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


def test_workflow_resumes_once_and_rejects_duplicate_approval(
    test_client, admin_headers, monkeypatch
):
    original = _enable_create_user()
    calls = 0

    async def fake_execute(tool, arguments, context):
        nonlocal calls
        calls += 1
        return {"success": True, "output": {"username": arguments["username"]}}

    monkeypatch.setattr("app.workflows.engine.execute_tool", fake_execute)
    try:
        conv = test_client.post(
            "/api/agent/conversations",
            headers=admin_headers,
            json={"agent_id": "default", "title": "resume"},
        ).json()["data"]
        start_response = test_client.post(
            "/api/agent/chat/aisdk",
            headers=admin_headers,
            json={
                "id": conv["conversation_id"],
                "messages": [{"role": "user", "parts": [{"type": "text", "text": "创建一个用户"}]}],
            },
        )
        run = get_workflow_store().get_active_for_conversation(
            conv["conversation_id"], "tenant-a", "admin-001"
        )
        assert run["status"] == "waiting_input"
        workflow_message_id = f"workflow-msg-{run['run_id']}"
        assert f'"messageId": "{workflow_message_id}"' in start_response.text
        assert f'"id": "{run["run_id"]}"' in start_response.text
        input_id = run["interrupts"][-1]["interrupt_id"]
        input_response = test_client.post(
            "/api/agent/chat/aisdk",
            headers=admin_headers,
            json={
                "id": conv["conversation_id"],
                "messages": [{
                    "role": "assistant",
                    "parts": [{
                        "type": "tool-workflow_control",
                        "toolCallId": f"workflow_{input_id}",
                        "approval": {
                            "id": input_id,
                            "approved": True,
                            "reason": json.dumps({
                                "username": "once",
                                "email": "once@example.com",
                                "role": "user",
                            }),
                        },
                    }],
                }],
            },
        )
        run = get_workflow_store().get_active_for_conversation(
            conv["conversation_id"], "tenant-a", "admin-001"
        )
        approval_id = run["interrupts"][-1]["interrupt_id"]
        assert run["status"] == "waiting_approval"
        assert f'"messageId": "{workflow_message_id}"' in input_response.text
        assert f'"id": "{run["run_id"]}"' in input_response.text
        intermediate = get_conversation_store().get_conversation(
            conv["conversation_id"], "tenant-a"
        )
        assert intermediate is not None
        intermediate_workflow_messages = [
            message
            for message in intermediate.messages
            if any(
                part.get("type") == "data-workflow"
                for part in message.parts
                if isinstance(part, dict)
            )
        ]
        assert len(intermediate_workflow_messages) == 1
        assert intermediate_workflow_messages[0].message_id == workflow_message_id
        approval_body = {
            "id": conv["conversation_id"],
            "messages": [{
                "role": "assistant",
                "parts": [{
                    "type": "tool-workflow_control",
                    "toolCallId": f"workflow_{approval_id}",
                    "approval": {"id": approval_id, "approved": True, "reason": "{}"},
                }],
            }],
        }
        completion_response = test_client.post(
            "/api/agent/chat/aisdk", headers=admin_headers, json=approval_body
        )
        duplicate_response = test_client.post(
            "/api/agent/chat/aisdk", headers=admin_headers, json=approval_body
        )
        completed = get_workflow_store().get_run(run["run_id"])
        duplicate = get_workflow_store().get_run(run["run_id"])
        assert completed["status"] == duplicate["status"] == "completed"
        assert f'"messageId": "{workflow_message_id}"' in completion_response.text
        assert f'"messageId": "{workflow_message_id}"' in duplicate_response.text
        assert calls == 1

        history = get_conversation_store().get_conversation(
            conv["conversation_id"], "tenant-a"
        )
        assert history is not None
        workflow_messages = [
            message
            for message in history.messages
            if any(
                part.get("type") == "data-workflow"
                for part in message.parts
                if isinstance(part, dict)
            )
        ]
        assert len(workflow_messages) == 1
        assert workflow_messages[0].message_id == workflow_message_id
        workflow_parts = workflow_messages[0].parts
        snapshots = [
            part for part in workflow_parts if part.get("type") == "data-workflow"
        ]
        assert len(snapshots) == 1
        assert snapshots[0]["id"] == run["run_id"]
        assert snapshots[0]["data"]["status"] == "completed"
        assert not any(
            part.get("type") == "tool-workflow_control" for part in workflow_parts
        )
        assert not any(part.get("type") == "text" for part in workflow_parts)
    finally:
        get_agent_config_store().save_config(original)


def test_workflow_rejection_updates_the_canonical_message(
    test_client, admin_headers
):
    original = _enable_create_user()
    try:
        conv = test_client.post(
            "/api/agent/conversations",
            headers=admin_headers,
            json={"agent_id": "default", "title": "reject"},
        ).json()["data"]
        test_client.post(
            "/api/agent/chat/aisdk",
            headers=admin_headers,
            json={
                "id": conv["conversation_id"],
                "messages": [
                    {
                        "role": "user",
                        "parts": [{"type": "text", "text": "创建一个用户"}],
                    }
                ],
            },
        )
        run = get_workflow_store().get_active_for_conversation(
            conv["conversation_id"], "tenant-a", "admin-001"
        )
        interrupt_id = run["interrupts"][-1]["interrupt_id"]
        response = test_client.post(
            "/api/agent/chat/aisdk",
            headers=admin_headers,
            json={
                "id": conv["conversation_id"],
                "messages": [
                    {
                        "role": "assistant",
                        "parts": [
                            {
                                "type": "tool-workflow_control",
                                "toolCallId": f"workflow_{interrupt_id}",
                                "approval": {
                                    "id": interrupt_id,
                                    "approved": False,
                                    "reason": "用户取消",
                                },
                            }
                        ],
                    }
                ],
            },
        )
        rejected = get_workflow_store().get_run(run["run_id"])
        assert rejected["status"] == "cancelled"
        assert f'"messageId": "workflow-msg-{run["run_id"]}"' in response.text

        history = get_conversation_store().get_conversation(
            conv["conversation_id"], "tenant-a"
        )
        assert history is not None
        workflow_messages = [
            message
            for message in history.messages
            if any(
                part.get("type") == "data-workflow"
                for part in message.parts
                if isinstance(part, dict)
            )
        ]
        assert len(workflow_messages) == 1
        parts = workflow_messages[0].parts
        assert next(
            part for part in parts if part.get("type") == "data-workflow"
        )["data"]["status"] == "cancelled"
        assert not any(
            part.get("type") == "tool-workflow_control" for part in parts
        )
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


def test_workflow_api_rbac_history_and_conversation_lock(
    test_client, admin_headers, demo_headers
):
    original = _enable_create_user()
    try:
        conv = test_client.post(
            "/api/agent/conversations",
            headers=admin_headers,
            json={"agent_id": "default", "title": "workflow api"},
        ).json()["data"]
        body = {
            "id": conv["conversation_id"],
            "messages": [{
                "id": "user-workflow",
                "role": "user",
                "parts": [{"type": "text", "text": "创建一个用户"}],
            }],
        }
        response = test_client.post(
            "/api/agent/chat/aisdk", headers=admin_headers, json=body
        )
        assert response.status_code == 200
        assert '"type": "data-workflow"' in response.text
        assert '"type": "tool-approval-request"' in response.text

        run = get_workflow_store().get_active_for_conversation(
            conv["conversation_id"], "tenant-a", "admin-001"
        )
        assert run and run["status"] == "waiting_input"
        assert test_client.get(
            f"/api/agent/workflows/{run['run_id']}", headers=demo_headers
        ).status_code == 404
        assert test_client.post(
            "/api/agent/chat/aisdk", headers=admin_headers, json=body
        ).status_code == 409

        history = test_client.get(
            f"/api/agent/conversations/{conv['conversation_id']}",
            headers=admin_headers,
        ).json()["data"]
        assert any(
            part.get("type") == "data-workflow"
            for message in history["messages"]
            for part in message["parts"]
        )
        cancelled = test_client.post(
            f"/api/agent/workflows/{run['run_id']}/cancel", headers=admin_headers
        )
        assert cancelled.status_code == 200
        assert cancelled.json()["data"]["status"] == "cancelled"
        cancelled_history = test_client.get(
            f"/api/agent/conversations/{conv['conversation_id']}",
            headers=admin_headers,
        ).json()["data"]
        cancelled_parts = [
            part
            for message in cancelled_history["messages"]
            for part in message["parts"]
            if part.get("type") in {"data-workflow", "tool-workflow_control"}
        ]
        assert len(
            [part for part in cancelled_parts if part["type"] == "data-workflow"]
        ) == 1
        assert not any(
            part["type"] == "tool-workflow_control" for part in cancelled_parts
        )
    finally:
        get_agent_config_store().save_config(original)
