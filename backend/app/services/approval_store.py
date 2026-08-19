"""SQLite-backed tool approval state transitions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.sqlite import connect, initialize_database, transaction


class ApprovalStore:
    """Persist approvals and enforce one-time consumption."""

    def __init__(self) -> None:
        initialize_database()

    def create(
        self,
        approval_id: str,
        tool_call_id: str,
        conversation_id: str,
        action: dict[str, Any],
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with transaction() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO tool_approvals(
                    approval_id, tool_call_id, conversation_id, action_json,
                    status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    approval_id,
                    tool_call_id,
                    conversation_id,
                    json.dumps(action, ensure_ascii=False),
                    now,
                    now,
                ),
            )
        approval = self.get(approval_id, conversation_id)
        if approval is None:
            raise RuntimeError("approval creation failed")
        return approval

    def get(
        self, approval_id: str, conversation_id: str
    ) -> Optional[dict[str, Any]]:
        conn = connect()
        try:
            row = conn.execute(
                "SELECT * FROM tool_approvals WHERE approval_id=? AND conversation_id=?",
                (approval_id, conversation_id),
            ).fetchone()
        finally:
            conn.close()
        return self._row_to_dict(row) if row else None

    @staticmethod
    def _row_to_dict(row: Any) -> dict[str, Any]:
        return {
            "approval_id": row["approval_id"],
            "tool_call_id": row["tool_call_id"],
            "conversation_id": row["conversation_id"],
            "action": json.loads(row["action_json"]),
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def respond(
        self,
        approval_id: str,
        conversation_id: str,
        approved: bool,
        reason: str = "",
    ) -> Optional[dict[str, Any]]:
        """Move pending to approved/rejected; repeated responses are idempotent."""
        target = "approved" if approved else "rejected"
        now = datetime.now(timezone.utc).isoformat()
        with transaction() as conn:
            row = conn.execute(
                """
                SELECT action_json, status FROM tool_approvals
                WHERE approval_id=? AND conversation_id=?
                """,
                (approval_id, conversation_id),
            ).fetchone()
            if row is None:
                return None
            if row["status"] == "pending":
                action = json.loads(row["action_json"])
                if reason:
                    action["approval_reason"] = reason
                conn.execute(
                    """
                    UPDATE tool_approvals
                    SET status=?, action_json=?, updated_at=?
                    WHERE approval_id=? AND conversation_id=? AND status='pending'
                    """,
                    (
                        target,
                        json.dumps(action, ensure_ascii=False),
                        now,
                        approval_id,
                        conversation_id,
                    ),
                )
        return self.get(approval_id, conversation_id)

    def consume(
        self, approval_id: str, conversation_id: str
    ) -> Optional[dict[str, Any]]:
        """Atomically claim an approved action for exactly-once execution."""
        now = datetime.now(timezone.utc).isoformat()
        with transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE tool_approvals SET status='consumed', updated_at=?
                WHERE approval_id=? AND conversation_id=? AND status='approved'
                """,
                (now, approval_id, conversation_id),
            )
            if cursor.rowcount != 1:
                return None
            row = conn.execute(
                "SELECT * FROM tool_approvals WHERE approval_id=?",
                (approval_id,),
            ).fetchone()
        return self._row_to_dict(row)


_approval_store: Optional[ApprovalStore] = None


def get_approval_store() -> ApprovalStore:
    global _approval_store
    if _approval_store is None:
        _approval_store = ApprovalStore()
    return _approval_store


def reset_approval_store() -> None:
    global _approval_store
    _approval_store = None
