"""SQLite persistence, isolation, and approval transition tests."""

import json
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.agent.prompts import DEMO_SYSTEM_PROMPT, LEGACY_DEFAULT_SYSTEM_PROMPT
from app.config import settings
from app.core.sqlite import connect, initialize_database, transaction
from app.models.agent import ConversationMessage
from app.services.approval_store import ApprovalStore
from app.services.conversation_store import ConversationStore


def test_conversation_survives_store_recreation():
    store = ConversationStore()
    conv = store.create_conversation("persist-tenant", "persist-user", "default")
    message = ConversationMessage(role="user", content="持久化消息")
    store.add_message(conv.conversation_id, message)

    recreated = ConversationStore().get_conversation_for_user(
        conv.conversation_id, "persist-tenant", "persist-user"
    )
    assert recreated is not None
    assert recreated.messages[0].message_id == message.message_id
    assert recreated.messages[0].parts == [{"type": "text", "text": "持久化消息"}]


def test_schema_v5_upgrades_only_untouched_default_agent_prompts(
    tmp_path, monkeypatch
):
    database = tmp_path / "agent-prompt-v5.db"
    monkeypatch.setattr(settings, "database_path", str(database))
    initialize_database()

    custom_prompt = "保留管理员自定义提示词"
    with transaction() as conn:
        conn.execute("DELETE FROM schema_version WHERE version=5")
        for tenant_id, prompt in (
            ("tenant-legacy", LEGACY_DEFAULT_SYSTEM_PROMPT),
            ("tenant-custom", custom_prompt),
        ):
            conn.execute(
                """
                INSERT INTO agent_configs(
                    tenant_id, agent_id, name, description, model,
                    system_prompt, temperature, max_tokens,
                    created_at, updated_at
                ) VALUES (?, 'default', '默认助手', '', 'deepseek-v4-pro',
                          ?, 0.7, 4096,
                          '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
                """,
                (tenant_id, prompt),
            )

    initialize_database()
    conn = connect()
    try:
        prompts = {
            row["tenant_id"]: row["system_prompt"]
            for row in conn.execute(
                "SELECT tenant_id, system_prompt FROM agent_configs"
            ).fetchall()
        }
        assert conn.execute(
            "SELECT 1 FROM schema_version WHERE version=5"
        ).fetchone()
    finally:
        conn.close()

    assert prompts == {
        "tenant-legacy": DEMO_SYSTEM_PROMPT,
        "tenant-custom": custom_prompt,
    }

    initialize_database()
    conn = connect()
    try:
        repeated_prompts = {
            row["tenant_id"]: row["system_prompt"]
            for row in conn.execute(
                "SELECT tenant_id, system_prompt FROM agent_configs"
            ).fetchall()
        }
    finally:
        conn.close()
    assert repeated_prompts == prompts


def test_conversation_foreign_keys_cascade():
    store = ConversationStore()
    conv = store.create_conversation("cascade-tenant", "cascade-user", "default")
    store.add_message(conv.conversation_id, ConversationMessage(role="user", content="x"))
    assert store.delete_conversation_for_user(
        conv.conversation_id, "cascade-tenant", "cascade-user"
    )
    conn = connect()
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM conversation_messages WHERE conversation_id=?",
            (conv.conversation_id,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 0


def test_concurrent_message_writes():
    store = ConversationStore()
    conv = store.create_conversation("write-tenant", "write-user", "default")

    def write(index: int) -> None:
        store.add_message(
            conv.conversation_id,
            ConversationMessage(role="user", content=f"message-{index}"),
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(write, range(8)))

    restored = store.get_conversation(conv.conversation_id, "write-tenant")
    assert restored is not None
    assert len(restored.messages) == 8


def test_approval_is_consumed_once():
    store = ConversationStore()
    conv = store.create_conversation("approval-tenant", "approval-user", "default")
    approvals = ApprovalStore()
    suffix = uuid.uuid4().hex
    approval_id = f"approval-{suffix}"
    approvals.create(
        approval_id,
        f"call-{suffix}",
        conv.conversation_id,
        {"intent_label": "single_delete"},
    )
    assert approvals.respond(approval_id, conv.conversation_id, True)["status"] == "approved"
    assert approvals.consume(approval_id, conv.conversation_id)["status"] == "consumed"
    assert approvals.consume(approval_id, conv.conversation_id) is None


def test_schema_v4_collapses_duplicate_workflow_messages(tmp_path, monkeypatch):
    database = tmp_path / "workflow-v4.db"
    monkeypatch.setattr(settings, "database_path", str(database))
    initialize_database()

    run_id = "run-v4"
    pending_id = "interrupt-current"
    old_control = {
        "type": "tool-workflow_control",
        "toolCallId": "workflow_interrupt-old",
        "input": {
            "run_id": run_id,
            "interrupt_id": "interrupt-old",
            "kind": "input",
        },
    }
    current_control = {
        "type": "tool-workflow_control",
        "toolCallId": f"workflow_{pending_id}",
        "state": "approval-requested",
        "input": {
            "run_id": run_id,
            "interrupt_id": pending_id,
            "kind": "approval",
        },
        "approval": {"id": pending_id},
    }
    snapshots = {
        1: {"run_id": run_id, "version": 1, "pending_interrupt": None},
        2: {"run_id": run_id, "version": 2, "pending_interrupt": None},
        3: {
            "run_id": run_id,
            "version": 3,
            "pending_interrupt": {"interrupt_id": pending_id},
        },
    }
    with transaction() as conn:
        conn.execute("DELETE FROM schema_version WHERE version=4")
        conn.execute(
            """
            INSERT INTO conversations(
                conversation_id, tenant_id, user_id, agent_id, title,
                created_at, updated_at
            ) VALUES ('conv-v4', 'tenant-v4', 'user-v4', 'default', 'v4',
                      '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
            """
        )
        rows = [
            (
                "message-anchor",
                "保留正文",
                [
                    {"type": "text", "text": "保留正文"},
                    {"type": "data-workflow", "data": snapshots[1]},
                    old_control,
                ],
                "2026-01-01T00:00:01Z",
            ),
            (
                "message-mixed",
                "保留第二条",
                [
                    {"type": "data-workflow", "data": snapshots[3]},
                    current_control,
                    {"type": "text", "text": "保留第二条"},
                ],
                "2026-01-01T00:00:02Z",
            ),
            (
                "message-empty",
                "",
                [
                    {"type": "data-workflow", "data": snapshots[2]},
                    old_control,
                ],
                "2026-01-01T00:00:03Z",
            ),
        ]
        for message_id, content, parts, created_at in rows:
            tool_calls = [
                part
                for part in parts
                if str(part.get("type", "")).startswith("tool-")
            ]
            conn.execute(
                """
                INSERT INTO conversation_messages(
                    message_id, conversation_id, role, content,
                    tool_calls_json, tool_call_id, reasoning,
                    a2ui_schemas_json, parts_json, created_at
                ) VALUES (?, 'conv-v4', 'assistant', ?, ?, '', '', '[]', ?, ?)
                """,
                (
                    message_id,
                    content,
                    json.dumps(tool_calls),
                    json.dumps(parts),
                    created_at,
                ),
            )

    initialize_database()
    conn = connect()
    try:
        migrated_rows = conn.execute(
            """
            SELECT message_id, parts_json FROM conversation_messages
            WHERE conversation_id='conv-v4' ORDER BY created_at, rowid
            """
        ).fetchall()
        assert conn.execute(
            "SELECT 1 FROM schema_version WHERE version=4"
        ).fetchone()
    finally:
        conn.close()

    assert [row["message_id"] for row in migrated_rows] == [
        "message-anchor",
        "message-mixed",
    ]
    anchor_parts = json.loads(migrated_rows[0]["parts_json"])
    workflow_parts = [
        part for part in anchor_parts if part.get("type") == "data-workflow"
    ]
    assert len(workflow_parts) == 1
    assert workflow_parts[0]["id"] == run_id
    assert workflow_parts[0]["data"]["version"] == 3
    assert current_control in anchor_parts
    assert {"type": "text", "text": "保留正文"} in anchor_parts
    assert json.loads(migrated_rows[1]["parts_json"]) == [
        {"type": "text", "text": "保留第二条"}
    ]

    before_second_start = [tuple(row) for row in migrated_rows]
    initialize_database()
    conn = connect()
    try:
        after_second_start = [
            tuple(row)
            for row in conn.execute(
                """
                SELECT message_id, parts_json FROM conversation_messages
                WHERE conversation_id='conv-v4' ORDER BY created_at, rowid
                """
            ).fetchall()
        ]
    finally:
        conn.close()
    assert after_second_start == before_second_start


def test_schema_v4_migration_rolls_back_on_invalid_parts(tmp_path, monkeypatch):
    database = tmp_path / "workflow-v4-invalid.db"
    monkeypatch.setattr(settings, "database_path", str(database))
    initialize_database()
    with transaction() as conn:
        conn.execute("DELETE FROM schema_version WHERE version=4")
        conn.execute(
            """
            INSERT INTO conversations(
                conversation_id, tenant_id, user_id, agent_id, title,
                created_at, updated_at
            ) VALUES ('conv-invalid', 'tenant-v4', 'user-v4', 'default', 'v4',
                      '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
            """
        )
        conn.execute(
            """
            INSERT INTO conversation_messages(
                message_id, conversation_id, role, content,
                tool_calls_json, tool_call_id, reasoning,
                a2ui_schemas_json, parts_json, created_at
            ) VALUES ('message-invalid', 'conv-invalid', 'assistant', '',
                      '[]', '', '', '[]', '{invalid', '2026-01-01T00:00:01Z')
            """
        )

    with pytest.raises(json.JSONDecodeError):
        initialize_database()

    conn = connect()
    try:
        assert conn.execute(
            "SELECT 1 FROM schema_version WHERE version=4"
        ).fetchone() is None
        assert conn.execute(
            """
            SELECT parts_json FROM conversation_messages
            WHERE message_id='message-invalid'
            """
        ).fetchone()["parts_json"] == "{invalid"
    finally:
        conn.close()
