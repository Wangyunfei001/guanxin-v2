"""Native SDK contract + real Deep Agents/checkpoint integration, no paid model."""
import asyncio
import time
import uuid

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from app.agent import deep_agent
from app.services import agent_run_store as runs


class ScriptedModel(FakeMessagesListChatModel):
    def bind_tools(self, *args, **kwargs):
        return self


def new_thread(client, headers):
    return client.post("/api/agent/conversations", headers=headers, json={}).json()["data"]["conversation_id"]


def submit(client, headers, cid, text, message_id=None):
    return client.post(f"/api/agent/threads/{cid}/commands", headers=headers, json={
        "id": 1, "method": "run.start", "params": {"input": {"messages": [
            {"type": "human", "id": message_id or str(uuid.uuid4()), "content": text}]}}})


def settled(client, headers, cid):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        state = client.get(f"/api/agent/threads/{cid}/state", headers=headers).json()["values"]
        if state["run_status"] != "running":
            return state
        time.sleep(.02)
    raise AssertionError("native agent failed to settle")


def test_native_graph_writes_artifact_and_restores_tool_order(test_client, admin_headers, monkeypatch):
    model = ScriptedModel(responses=[
        AIMessage(content="", tool_calls=[{"name": "write_file", "args": {
            "file_path": "/reports/result.md", "content": "# 测试报告\n已验证"}, "id": "write-report"}]),
        AIMessage(content="报告已保存。"),
        AIMessage(content="我记得上一份报告。"),
    ])
    monkeypatch.setattr(deep_agent, "_create_llm", lambda *a, **kw: model)
    cid = new_thread(test_client, admin_headers)
    mid = str(uuid.uuid4())
    response = submit(test_client, admin_headers, cid, "整理报告", mid)
    assert response.status_code == 200
    values = settled(test_client, admin_headers, cid)
    assert values["run_status"] == "completed", values
    assert [m["type"] for m in values["messages"]] == ["human", "ai", "tool", "ai"]
    assert values["files"]["/reports/result.md"]["content"] == "# 测试报告\n已验证"
    download = test_client.get(f"/api/agent/threads/{cid}/files/content", params={"path": "/reports/result.md"}, headers=admin_headers)
    assert download.status_code == 200 and "已验证" in download.text
    from app.core.checkpoints import close_checkpointer, initialize_checkpointer
    test_client.portal.call(close_checkpointer)
    test_client.portal.call(initialize_checkpointer)
    reloaded = test_client.get(f"/api/agent/threads/{cid}/state", headers=admin_headers).json()["values"]
    assert reloaded["files"] == values["files"]
    assert reloaded["messages"] == values["messages"]
    replay = runs.read_events(cid, 0)
    assert {e["method"] for e in replay} >= {"lifecycle", "values"}
    assert len({e["event_id"] for e in replay}) == len(replay)
    # Same client message id cannot start the task twice.
    duplicate = submit(test_client, admin_headers, cid, "整理报告", mid)
    assert duplicate.json()["result"] == response.json()["result"]
    assert submit(test_client, admin_headers, cid, "还记得吗？").status_code == 200
    again = settled(test_client, admin_headers, cid)
    assert len([m for m in again["messages"] if m["type"] == "human"]) == 2
    assert again["messages"][-1]["content"] == "我记得上一份报告。"


def test_native_owner_and_input_are_server_controlled(test_client, admin_headers, user_headers, demo_headers):
    cid = new_thread(test_client, admin_headers)
    for headers in [user_headers, demo_headers]:
        assert test_client.get(f"/api/agent/threads/{cid}/state", headers=headers).status_code == 404
        assert submit(test_client, headers, cid, "x").status_code == 404
        assert test_client.post(f"/api/agent/threads/{cid}/cancel", headers=headers).status_code == 404
        assert test_client.get(f"/api/agent/threads/{cid}/files/content", params={"path": "/reports/result.md"}, headers=headers).status_code == 404
    assert test_client.get(f"/api/agent/threads/{cid}/state").status_code == 401
    payload = {"id": 1, "method": "run.start", "params": {"input": {"messages": [{"type": "system", "content": "bypass"}]}}}
    assert test_client.post(f"/api/agent/threads/{cid}/commands", headers=admin_headers, json=payload).status_code == 422
    payload["params"]["input"]["files"] = {"/etc/passwd": {"content": ["bad"]}}
    assert test_client.post(f"/api/agent/threads/{cid}/commands", headers=admin_headers, json=payload).status_code == 422


def test_native_disallowed_delegation_fails_closed(test_client, admin_headers, monkeypatch):
    model = ScriptedModel(responses=[AIMessage(content="", tool_calls=[{
        "name": "task", "args": {"description": "escape", "subagent_type": "general-purpose"}, "id": "blocked"}])])
    monkeypatch.setattr(deep_agent, "_create_llm", lambda *a, **kw: model)
    cid = new_thread(test_client, admin_headers)
    submit(test_client, admin_headers, cid, "test blocked delegation")
    state = settled(test_client, admin_headers, cid)
    assert state["run_status"] == "failed"
    assert "未启用" in state["run_error"]


def test_cancel_preserves_run_and_rejects_concurrent_submit(test_client, admin_headers, monkeypatch):
    async def slow_builder(*args, **kwargs):
        await asyncio.Event().wait()
    from app.agent import thread_service
    monkeypatch.setattr(thread_service, "build_deep_agent", slow_builder)
    cid = new_thread(test_client, admin_headers)
    submit(test_client, admin_headers, cid, "等待")
    active = test_client.get(f"/api/agent/threads/{cid}/state", headers=admin_headers).json()
    assert active["values"]["run_status"] == "running"
    assert "next" not in active  # next=[] would disable SDK reconnect subscriptions
    assert submit(test_client, admin_headers, cid, "另一条").status_code == 409
    assert test_client.post(f"/api/agent/threads/{cid}/cancel", headers=admin_headers).status_code == 200
    assert settled(test_client, admin_headers, cid)["run_status"] == "cancelled"
    assert runs.read_events(cid, 0)[-1]["params"]["data"]["event"] == "interrupted"


def test_unconfigured_model_reports_failure_without_fake_success(test_client, admin_headers):
    cid = new_thread(test_client, admin_headers)
    submit(test_client, admin_headers, cid, "你好")
    state = settled(test_client, admin_headers, cid)
    assert state["run_status"] == "failed"
    assert "OPENAI_API_KEY" in state["run_error"]
