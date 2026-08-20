"""对话存储模块。

管理持久化对话历史和消息记录。
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from app.core.sqlite import connect, initialize_database, transaction
from app.models.agent import Conversation, ConversationMessage


class ConversationStore:
    """SQLite 对话存储管理器。"""

    def __init__(self) -> None:
        initialize_database()

    @staticmethod
    def _message_from_row(row: Any) -> ConversationMessage:
        return ConversationMessage(
            message_id=row["message_id"],
            role=row["role"],
            content=row["content"],
            tool_calls=json.loads(row["tool_calls_json"] or "[]"),
            tool_call_id=row["tool_call_id"],
            reasoning=row["reasoning"],
            a2ui_schemas=json.loads(row["a2ui_schemas_json"] or "[]"),
            parts=json.loads(row["parts_json"] or "[]"),
            created_at=row["created_at"],
        )

    def _conversation_from_row(self, row: Any, include_messages: bool = True) -> Conversation:
        messages = (
            self.get_messages(row["conversation_id"], row["tenant_id"])
            if include_messages
            else []
        )
        return Conversation(
            conversation_id=row["conversation_id"],
            tenant_id=row["tenant_id"],
            user_id=row["user_id"],
            agent_id=row["agent_id"],
            title=row["title"],
            messages=messages,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def create_conversation(
        self,
        tenant_id: str,
        user_id: str,
        agent_id: str,
        title: str = "",
    ) -> Conversation:
        """创建新对话。"""
        conversation_id = str(uuid.uuid4())
        conv = Conversation(
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            user_id=user_id,
            agent_id=agent_id,
            title=title or "新对话",
        )
        with transaction() as conn:
            conn.execute(
                """
                INSERT INTO conversations(
                    conversation_id, tenant_id, user_id, agent_id, title,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conv.conversation_id, conv.tenant_id, conv.user_id,
                    conv.agent_id, conv.title, conv.created_at, conv.updated_at,
                ),
            )
        return conv

    def get_conversation(
        self, conversation_id: str, tenant_id: str
    ) -> Optional[Conversation]:
        """获取对话（带租户校验）。"""
        conn = connect()
        try:
            row = conn.execute(
                "SELECT * FROM conversations WHERE conversation_id=? AND tenant_id=?",
                (conversation_id, tenant_id),
            ).fetchone()
        finally:
            conn.close()
        return self._conversation_from_row(row) if row else None

    def list_conversations(self, tenant_id: str, user_id: str = "") -> List[Conversation]:
        """列出对话。"""
        conn = connect()
        try:
            if user_id:
                rows = conn.execute(
                    """
                    SELECT * FROM conversations
                    WHERE tenant_id=? AND user_id=?
                    ORDER BY updated_at DESC
                    """,
                    (tenant_id, user_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM conversations
                    WHERE tenant_id=? ORDER BY updated_at DESC
                    """,
                    (tenant_id,),
                ).fetchall()
        finally:
            conn.close()
        return [self._conversation_from_row(row) for row in rows]

    def add_message(
        self, conversation_id: str, message: ConversationMessage
    ) -> Optional[Conversation]:
        """添加消息到对话。"""
        conn = connect()
        try:
            row = conn.execute(
                "SELECT tenant_id FROM conversations WHERE conversation_id=?",
                (conversation_id,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        now = datetime.now(timezone.utc).isoformat()
        with transaction() as conn:
            message_count = conn.execute(
                "SELECT COUNT(*) FROM conversation_messages WHERE conversation_id=?",
                (conversation_id,),
            ).fetchone()[0]
            conn.execute(
                """
                INSERT INTO conversation_messages(
                    message_id, conversation_id, role, content, tool_calls_json,
                    tool_call_id, reasoning, a2ui_schemas_json, parts_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.message_id,
                    conversation_id,
                    message.role,
                    message.content,
                    json.dumps(message.tool_calls, ensure_ascii=False),
                    message.tool_call_id,
                    message.reasoning,
                    json.dumps(message.a2ui_schemas, ensure_ascii=False),
                    json.dumps(message.parts or message._default_parts(), ensure_ascii=False),
                    message.created_at,
                ),
            )
            if message.role == "user" and message_count == 0:
                conn.execute(
                    """
                    UPDATE conversations SET updated_at=?, title=?
                    WHERE conversation_id=?
                    """,
                    (now, message.content.strip()[:30] or "新对话", conversation_id),
                )
            else:
                conn.execute(
                    "UPDATE conversations SET updated_at=? WHERE conversation_id=?",
                    (now, conversation_id),
                )
        return self.get_conversation(conversation_id, row["tenant_id"])

    def delete_conversation(self, conversation_id: str, tenant_id: str) -> bool:
        """删除对话。"""
        with transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM conversations WHERE conversation_id=? AND tenant_id=?",
                (conversation_id, tenant_id),
            )
            return cursor.rowcount > 0

    def get_messages(
        self, conversation_id: str, tenant_id: str
    ) -> List[ConversationMessage]:
        """获取对话消息列表。"""
        conn = connect()
        try:
            owner = conn.execute(
                "SELECT 1 FROM conversations WHERE conversation_id=? AND tenant_id=?",
                (conversation_id, tenant_id),
            ).fetchone()
            if owner is None:
                return []
            rows = conn.execute(
                """
                SELECT * FROM conversation_messages
                WHERE conversation_id=? ORDER BY created_at, rowid
                """,
                (conversation_id,),
            ).fetchall()
            return [self._message_from_row(row) for row in rows]
        finally:
            conn.close()

    def get_conversation_for_user(
        self, conversation_id: str, tenant_id: str, user_id: str
    ) -> Optional[Conversation]:
        """按租户和用户校验对话归属。"""
        conv = self.get_conversation(conversation_id, tenant_id)
        if conv and conv.user_id == user_id:
            return conv
        return None

    def delete_conversation_for_user(
        self, conversation_id: str, tenant_id: str, user_id: str
    ) -> bool:
        """Delete only when both tenant and user own the conversation."""
        with transaction() as conn:
            cursor = conn.execute(
                """
                DELETE FROM conversations
                WHERE conversation_id=? AND tenant_id=? AND user_id=?
                """,
                (conversation_id, tenant_id, user_id),
            )
            return cursor.rowcount > 0

    def update_approval_part(
        self,
        conversation_id: str,
        approval_id: str,
        approved: bool,
        reason: str = "",
        output: Any = None,
    ) -> bool:
        """Update the persisted tool part that owns an approval ID."""
        with transaction() as conn:
            rows = conn.execute(
                """
                SELECT message_id, parts_json, tool_calls_json
                FROM conversation_messages WHERE conversation_id=?
                ORDER BY created_at DESC
                """,
                (conversation_id,),
            ).fetchall()
            for row in rows:
                parts = json.loads(row["parts_json"] or "[]")
                changed = False
                for part in parts:
                    approval = part.get("approval") if isinstance(part, dict) else None
                    if isinstance(approval, dict) and approval.get("id") == approval_id:
                        part["approval"] = {
                            **approval,
                            "approved": approved,
                            **({"reason": reason} if reason else {}),
                        }
                        if approved and output is not None:
                            part["state"] = "output-available"
                            part["output"] = output
                        elif approved:
                            part["state"] = "approval-responded"
                        else:
                            part["state"] = "output-denied"
                        changed = True
                        break
                if changed:
                    conn.execute(
                        """
                        UPDATE conversation_messages
                        SET parts_json=?, tool_calls_json=? WHERE message_id=?
                        """,
                        (
                            json.dumps(parts, ensure_ascii=False),
                            json.dumps(parts, ensure_ascii=False),
                            row["message_id"],
                        ),
                    )
                    return True
        return False

    def update_workflow_part(
        self,
        conversation_id: str,
        run_id: str,
        data: dict[str, Any],
    ) -> bool:
        """Replace the persisted data-workflow snapshot for a run."""
        with transaction() as conn:
            rows = conn.execute(
                """
                SELECT message_id, parts_json FROM conversation_messages
                WHERE conversation_id=? ORDER BY created_at
                """,
                (conversation_id,),
            ).fetchall()
            for row in rows:
                parts = json.loads(row["parts_json"] or "[]")
                for part in parts:
                    if (
                        isinstance(part, dict)
                        and part.get("type") == "data-workflow"
                        and isinstance(part.get("data"), dict)
                        and part["data"].get("run_id") == run_id
                    ):
                        part["data"] = data
                        conn.execute(
                            "UPDATE conversation_messages SET parts_json=? WHERE message_id=?",
                            (json.dumps(parts, ensure_ascii=False), row["message_id"]),
                        )
                        return True
        return False


# 全局单例
_conversation_store: Optional[ConversationStore] = None


def get_conversation_store() -> ConversationStore:
    """获取全局对话存储单例。"""
    global _conversation_store
    if _conversation_store is None:
        _conversation_store = ConversationStore()
    return _conversation_store


def reset_conversation_store() -> None:
    """重置对话存储（用于测试）。"""
    global _conversation_store
    _conversation_store = None
