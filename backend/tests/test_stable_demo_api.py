"""Acceptance coverage for authenticated LangChain and Agent configuration APIs."""

from app.models.agent import ConversationMessage
from app.services.conversation_store import get_conversation_store


def _config_payload(config: dict) -> dict:
    return {
        "model": config["model"],
        "temperature": config["temperature"],
        "max_tokens": config["max_tokens"],
        "system_prompt": config["system_prompt"],
        "enabled_tools": config["enabled_tools"],
        "enabled_skills": config["enabled_skills"],
        "mcp_servers": config["mcp_servers"],
    }


def test_langchain_requires_authentication(test_client):
    response = test_client.post(
        "/api/agent/threads/missing/commands",
        json={"id": "missing", "messages": []},
    )
    assert response.status_code == 401


def test_langchain_hides_conversation_from_other_users(
    test_client, admin_headers, user_headers, demo_headers
):
    created = test_client.post(
        "/api/agent/conversations",
        headers=admin_headers,
        json={"agent_id": "default", "title": "private"},
    ).json()["data"]
    body = {
        "id": created["conversation_id"],
        "messages": [{"id": "u1", "role": "user", "parts": [{"type": "text", "text": "hi"}]}],
    }
    assert test_client.post(
        f"/api/agent/threads/{created['conversation_id']}/commands", headers=user_headers, json=body
    ).status_code == 404
    assert test_client.post(
        f"/api/agent/threads/{created['conversation_id']}/commands", headers=demo_headers, json=body
    ).status_code == 404


def test_conversation_history_returns_stable_parts(test_client, admin_headers):
    created = test_client.post(
        "/api/agent/conversations",
        headers=admin_headers,
        json={"agent_id": "default", "title": "parts"},
    ).json()["data"]
    message = ConversationMessage(
        role="assistant",
        content="done",
        reasoning="reason",
        tool_calls=[{
            "type": "tool-kb_retrieval",
            "toolCallId": "call-stable",
            "state": "output-available",
            "input": {"query": "q"},
            "output": {"sources": []},
        }],
        a2ui_schemas=[{"component_type": "list_card", "props": {"items": []}}],
    )
    get_conversation_store().add_message(created["conversation_id"], message)

    response = test_client.get(
        f"/api/agent/conversations/{created['conversation_id']}",
        headers=admin_headers,
    ).json()["data"]
    saved = response["messages"][0]
    assert saved["message_id"] == message.message_id
    assert saved["parts"][0] == {"type": "reasoning", "text": "reason"}
    assert any(part.get("toolCallId") == "call-stable" for part in saved["parts"])
    assert any(part.get("type") == "data-a2ui" for part in saved["parts"])


def test_agent_config_rbac_validation_and_persistence(
    test_client, admin_headers, user_headers
):
    original = test_client.get("/api/agent/config", headers=admin_headers).json()["data"]
    payload = _config_payload(original)

    assert test_client.put(
        "/api/agent/config", headers=user_headers, json=payload
    ).status_code == 403

    invalid = {**payload, "temperature": 3}
    assert test_client.put(
        "/api/agent/config", headers=admin_headers, json=invalid
    ).status_code == 422

    changed = {**payload, "system_prompt": "persisted prompt"}
    try:
        saved = test_client.put(
            "/api/agent/config", headers=admin_headers, json=changed
        )
        assert saved.status_code == 200
        reloaded = test_client.get(
            "/api/agent/config", headers=admin_headers
        ).json()["data"]
        assert reloaded["system_prompt"] == "persisted prompt"
    finally:
        test_client.put("/api/agent/config", headers=admin_headers, json=payload)


def test_mcp_management_is_admin_only(test_client, user_headers):
    response = test_client.post(
        "/api/mcp/servers",
        headers=user_headers,
        json={"name": "forbidden", "command": "python", "args": []},
    )
    assert response.status_code == 403


def test_legacy_approval_history_is_read_only(test_client, admin_headers):
    created = test_client.post(
        "/api/agent/conversations",
        headers=admin_headers,
        json={"agent_id": "default", "title": "approval"},
    ).json()["data"]
    approval_id = f"approval-{created['conversation_id']}"
    tool_call_id = f"call-{created['conversation_id']}"
    part = {
        "type": "tool-confirm_action",
        "toolCallId": tool_call_id,
        "state": "output-denied",
        "input": {"action": "test", "entities": {}},
        "approval": {"id": approval_id, "approved": False, "reason": "历史拒绝"},
    }
    get_conversation_store().add_message(
        created["conversation_id"],
        ConversationMessage(role="assistant", content="", parts=[part], tool_calls=[part]),
    )
    history = test_client.get(
        f"/api/agent/conversations/{created['conversation_id']}", headers=admin_headers
    ).json()["data"]
    assert history["messages"][0]["parts"][0]["state"] == "output-denied"
    assert history["messages"][0]["parts"][0]["toolCallId"] == tool_call_id
