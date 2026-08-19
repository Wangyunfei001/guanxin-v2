"""SQLite persistence, isolation, and approval transition tests."""

import uuid
from concurrent.futures import ThreadPoolExecutor

from app.core.sqlite import connect
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
