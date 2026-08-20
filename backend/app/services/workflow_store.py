"""SQLite repository for persistent Agent workflows."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.sqlite import connect, initialize_database, transaction


ACTIVE_STATUSES = {
    "planning",
    "running",
    "waiting_input",
    "waiting_approval",
    "uncertain",
}


class WorkflowConflictError(RuntimeError):
    """Raised when a conversation already owns an active workflow."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _loads(value: str, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except (TypeError, json.JSONDecodeError):
        return default


class WorkflowStore:
    """Persist workflow runs, steps, interrupts and execution attempts."""

    def __init__(self) -> None:
        initialize_database()

    @staticmethod
    def _step(row: Any) -> dict[str, Any]:
        database_step_id = row["step_id"]
        public_step_id = (
            database_step_id.split(":", 1)[1]
            if ":" in database_step_id
            else database_step_id
        )
        return {
            "step_id": public_step_id,
            "db_step_id": database_step_id,
            "position": row["position"],
            "title": row["title"],
            "tool_name": row["tool_name"],
            "tool_category": row["tool_category"],
            "arguments": _loads(row["args_json"], {}),
            "resolved_arguments": _loads(row["resolved_args_json"], {}),
            "risk": row["risk"],
            "status": row["status"],
            "attempt_count": row["attempt_count"],
            "idempotency_key": row["idempotency_key"],
            "result": _loads(row["result_json"], None),
            "error": row["error"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _interrupt(row: Any) -> dict[str, Any]:
        database_step_id = row["step_id"]
        return {
            "interrupt_id": row["interrupt_id"],
            "step_id": database_step_id.split(":", 1)[1] if ":" in database_step_id else database_step_id,
            "db_step_id": database_step_id,
            "kind": row["kind"],
            "status": row["status"],
            "payload": _loads(row["payload_json"], {}),
            "response": _loads(row["response_json"], {}),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def create_run(
        self,
        *,
        tenant_id: str,
        user_id: str,
        conversation_id: str,
        agent_id: str,
        goal: str,
        summary: str,
        plan: dict[str, Any],
        steps: list[dict[str, Any]],
        run_id: str | None = None,
    ) -> dict[str, Any]:
        run_id = run_id or str(uuid.uuid4())
        now = _now()
        try:
            with transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO workflow_runs(
                        run_id, tenant_id, user_id, conversation_id, agent_id,
                        goal, summary, plan_json, status, current_step_index,
                        checkpoint_thread_id, version, last_error, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'running', 0, ?, 1, '', ?, ?)
                    """,
                    (
                        run_id,
                        tenant_id,
                        user_id,
                        conversation_id,
                        agent_id,
                        goal,
                        summary,
                        _json(plan),
                        run_id,
                        now,
                        now,
                    ),
                )
                for position, step in enumerate(steps):
                    public_step_id = step.get("step_id") or f"step_{position + 1}"
                    step_id = f"{run_id}:{public_step_id}"
                    conn.execute(
                        """
                        INSERT INTO workflow_steps(
                            step_id, run_id, position, title, tool_name,
                            tool_category, args_json, resolved_args_json, risk,
                            status, attempt_count, idempotency_key, result_json,
                            error, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, '{}', ?, 'pending', 0, ?, 'null', '', ?, ?)
                        """,
                        (
                            step_id,
                            run_id,
                            position,
                            step["title"],
                            step["tool_name"],
                            step["tool_category"],
                            _json(step.get("arguments", {})),
                            step["risk"],
                            f"workflow:{run_id}:{public_step_id}",
                            now,
                            now,
                        ),
                    )
        except sqlite3.IntegrityError as exc:
            if "workflow_runs.conversation_id" in str(exc):
                raise WorkflowConflictError("会话已有活动工作流") from exc
            raise
        result = self.get_run(run_id, tenant_id, user_id)
        if result is None:
            raise RuntimeError("workflow creation failed")
        return result

    def get_run(
        self,
        run_id: str,
        tenant_id: str = "",
        user_id: str = "",
    ) -> Optional[dict[str, Any]]:
        clauses = ["run_id=?"]
        params: list[Any] = [run_id]
        if tenant_id:
            clauses.append("tenant_id=?")
            params.append(tenant_id)
        if user_id:
            clauses.append("user_id=?")
            params.append(user_id)
        conn = connect()
        try:
            row = conn.execute(
                f"SELECT * FROM workflow_runs WHERE {' AND '.join(clauses)}",
                params,
            ).fetchone()
            if row is None:
                return None
            step_rows = conn.execute(
                "SELECT * FROM workflow_steps WHERE run_id=? ORDER BY position",
                (run_id,),
            ).fetchall()
            interrupt_rows = conn.execute(
                "SELECT * FROM workflow_interrupts WHERE run_id=? ORDER BY created_at",
                (run_id,),
            ).fetchall()
        finally:
            conn.close()
        return {
            "run_id": row["run_id"],
            "tenant_id": row["tenant_id"],
            "user_id": row["user_id"],
            "conversation_id": row["conversation_id"],
            "agent_id": row["agent_id"],
            "goal": row["goal"],
            "summary": row["summary"],
            "plan": _loads(row["plan_json"], {}),
            "status": row["status"],
            "current_step_index": row["current_step_index"],
            "checkpoint_thread_id": row["checkpoint_thread_id"],
            "version": row["version"],
            "last_error": row["last_error"],
            "steps": [self._step(item) for item in step_rows],
            "interrupts": [self._interrupt(item) for item in interrupt_rows],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get_active_for_conversation(
        self, conversation_id: str, tenant_id: str, user_id: str
    ) -> Optional[dict[str, Any]]:
        conn = connect()
        try:
            row = conn.execute(
                """
                SELECT run_id FROM workflow_runs
                WHERE conversation_id=? AND tenant_id=? AND user_id=?
                  AND status IN ('planning','running','waiting_input','waiting_approval','uncertain')
                """,
                (conversation_id, tenant_id, user_id),
            ).fetchone()
        finally:
            conn.close()
        return self.get_run(row["run_id"], tenant_id, user_id) if row else None

    def list_run_ids_for_conversation(
        self, conversation_id: str, tenant_id: str, user_id: str
    ) -> list[str]:
        conn = connect()
        try:
            rows = conn.execute(
                """
                SELECT run_id FROM workflow_runs
                WHERE conversation_id=? AND tenant_id=? AND user_id=?
                """,
                (conversation_id, tenant_id, user_id),
            ).fetchall()
            return [row["run_id"] for row in rows]
        finally:
            conn.close()

    def get_interrupt(self, interrupt_id: str) -> Optional[dict[str, Any]]:
        conn = connect()
        try:
            row = conn.execute(
                "SELECT * FROM workflow_interrupts WHERE interrupt_id=?",
                (interrupt_id,),
            ).fetchone()
            if row is None:
                return None
            run_id = row["run_id"]
        finally:
            conn.close()
        value = self._interrupt(row)
        value["run_id"] = run_id
        return value

    def set_run_status(
        self,
        run_id: str,
        status: str,
        *,
        current_step_index: int | None = None,
        error: str = "",
    ) -> None:
        now = _now()
        with transaction() as conn:
            if current_step_index is None:
                conn.execute(
                    """
                    UPDATE workflow_runs
                    SET status=?, last_error=?, version=version+1, updated_at=?
                    WHERE run_id=?
                    """,
                    (status, error, now, run_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE workflow_runs
                    SET status=?, current_step_index=?, last_error=?,
                        version=version+1, updated_at=? WHERE run_id=?
                    """,
                    (status, current_step_index, error, now, run_id),
                )

    def update_step(
        self,
        step_id: str,
        *,
        status: str,
        resolved_arguments: dict[str, Any] | None = None,
        result: Any = None,
        error: str = "",
        increment_attempt: bool = False,
    ) -> None:
        assignments = ["status=?", "error=?", "updated_at=?"]
        values: list[Any] = [status, error, _now()]
        if resolved_arguments is not None:
            assignments.append("resolved_args_json=?")
            values.append(_json(resolved_arguments))
        if result is not None:
            assignments.append("result_json=?")
            values.append(_json(result))
        if increment_attempt:
            assignments.append("attempt_count=attempt_count+1")
        values.append(step_id)
        with transaction() as conn:
            conn.execute(
                f"UPDATE workflow_steps SET {', '.join(assignments)} WHERE step_id=?",
                values,
            )

    def create_interrupt(
        self,
        run_id: str,
        step_id: str,
        kind: str,
        payload: dict[str, Any],
        interrupt_id: str | None = None,
    ) -> dict[str, Any]:
        interrupt_id = interrupt_id or f"interrupt_{uuid.uuid4().hex}"
        now = _now()
        with transaction() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO workflow_interrupts(
                    interrupt_id, run_id, step_id, kind, status,
                    payload_json, response_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'pending', ?, '{}', ?, ?)
                """,
                (interrupt_id, run_id, step_id, kind, _json(payload), now, now),
            )
        run = self.get_run(run_id)
        if run is None:
            raise RuntimeError("workflow not found")
        return next(item for item in run["interrupts"] if item["interrupt_id"] == interrupt_id)

    def resolve_interrupt(
        self,
        interrupt_id: str,
        run_id: str,
        *,
        accepted: bool,
        response: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        now = _now()
        target = "resolved" if accepted else "rejected"
        with transaction() as conn:
            row = conn.execute(
                """
                SELECT * FROM workflow_interrupts
                WHERE interrupt_id=? AND run_id=?
                """,
                (interrupt_id, run_id),
            ).fetchone()
            if row is None:
                return None
            if row["status"] == "pending":
                conn.execute(
                    """
                    UPDATE workflow_interrupts
                    SET status=?, response_json=?, updated_at=?
                    WHERE interrupt_id=? AND status='pending'
                    """,
                    (target, _json(response), now, interrupt_id),
                )
            updated = conn.execute(
                "SELECT * FROM workflow_interrupts WHERE interrupt_id=?",
                (interrupt_id,),
            ).fetchone()
        return self._interrupt(updated)

    def begin_execution(self, run_id: str, step_id: str) -> tuple[str, Any]:
        """Atomically begin an attempt or return an already persisted result."""
        now = _now()
        with transaction() as conn:
            step = conn.execute(
                "SELECT * FROM workflow_steps WHERE step_id=? AND run_id=?",
                (step_id, run_id),
            ).fetchone()
            if step is None:
                raise RuntimeError("workflow step not found")
            if step["status"] == "completed":
                return "completed", _loads(step["result_json"], None)
            attempt = step["attempt_count"] + 1
            execution_id = str(uuid.uuid4())
            execution_key = f"{step['idempotency_key']}:attempt:{attempt}"
            conn.execute(
                """
                INSERT INTO workflow_step_executions(
                    execution_id, run_id, step_id, attempt, idempotency_key,
                    status, result_json, error, started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, 'executing', 'null', '', ?, NULL)
                """,
                (execution_id, run_id, step_id, attempt, execution_key, now),
            )
            conn.execute(
                """
                UPDATE workflow_steps
                SET status='executing', attempt_count=?, updated_at=? WHERE step_id=?
                """,
                (attempt, now, step_id),
            )
            conn.execute(
                "UPDATE workflow_runs SET status='running', version=version+1, updated_at=? WHERE run_id=?",
                (now, run_id),
            )
        return execution_id, None

    def finish_execution(
        self,
        execution_id: str,
        run_id: str,
        step_id: str,
        *,
        status: str,
        result: Any = None,
        error: str = "",
    ) -> None:
        now = _now()
        with transaction() as conn:
            conn.execute(
                """
                UPDATE workflow_step_executions
                SET status=?, result_json=?, error=?, completed_at=?
                WHERE execution_id=? AND run_id=? AND step_id=?
                """,
                (status, _json(result), error, now, execution_id, run_id, step_id),
            )
            conn.execute(
                """
                UPDATE workflow_steps
                SET status=?, result_json=?, error=?, updated_at=? WHERE step_id=?
                """,
                (status, _json(result), error, now, step_id),
            )

    def cancel(self, run_id: str) -> bool:
        now = _now()
        with transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE workflow_runs SET status='cancelled', version=version+1, updated_at=?
                WHERE run_id=? AND status IN (
                    'planning','running','waiting_input','waiting_approval','uncertain','failed'
                )
                """,
                (now, run_id),
            )
            conn.execute(
                """
                UPDATE workflow_steps SET status='cancelled', updated_at=?
                WHERE run_id=? AND status IN ('pending','waiting_input','waiting_approval')
                """,
                (now, run_id),
            )
            conn.execute(
                """
                UPDATE workflow_interrupts SET status='cancelled', updated_at=?
                WHERE run_id=? AND status='pending'
                """,
                (now, run_id),
            )
            return cursor.rowcount > 0

    def recover_inflight(self) -> int:
        """Recover read attempts and quarantine ambiguous side effects."""
        now = _now()
        recovered = 0
        with transaction() as conn:
            rows = conn.execute(
                """
                SELECT s.*, r.status AS run_status FROM workflow_steps s
                JOIN workflow_runs r ON r.run_id=s.run_id
                WHERE s.status='executing' AND r.status IN ('running','uncertain')
                """
            ).fetchall()
            for step in rows:
                recovered += 1
                if step["risk"] == "read" and step["attempt_count"] < 2:
                    conn.execute(
                        "UPDATE workflow_steps SET status='pending', updated_at=? WHERE step_id=?",
                        (now, step["step_id"]),
                    )
                    conn.execute(
                        "UPDATE workflow_runs SET status='running', updated_at=? WHERE run_id=?",
                        (now, step["run_id"]),
                    )
                    conn.execute(
                        """
                        UPDATE workflow_step_executions
                        SET status='failed', error='进程重启，允许只读步骤重试', completed_at=?
                        WHERE step_id=? AND status='executing'
                        """,
                        (now, step["step_id"]),
                    )
                else:
                    conn.execute(
                        "UPDATE workflow_steps SET status='uncertain', error='执行期间服务重启', updated_at=? WHERE step_id=?",
                        (now, step["step_id"]),
                    )
                    conn.execute(
                        "UPDATE workflow_runs SET status='uncertain', last_error='风险步骤执行状态不确定', updated_at=? WHERE run_id=?",
                        (now, step["run_id"]),
                    )
                    conn.execute(
                        """
                        UPDATE workflow_step_executions
                        SET status='uncertain', error='执行期间服务重启', completed_at=?
                        WHERE step_id=? AND status='executing'
                        """,
                        (now, step["step_id"]),
                    )
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO workflow_interrupts(
                            interrupt_id, run_id, step_id, kind, status,
                            payload_json, response_json, created_at, updated_at
                        ) VALUES (?, ?, ?, 'recovery', 'pending', ?, '{}', ?, ?)
                        """,
                        (
                            f"recovery_{step['run_id']}_{step['step_id']}",
                            step["run_id"],
                            step["step_id"],
                            _json({"reason": "风险步骤执行状态不确定"}),
                            now,
                            now,
                        ),
                    )
        return recovered


_workflow_store: Optional[WorkflowStore] = None


def get_workflow_store() -> WorkflowStore:
    global _workflow_store
    if _workflow_store is None:
        _workflow_store = WorkflowStore()
    return _workflow_store


def reset_workflow_store() -> None:
    global _workflow_store
    _workflow_store = None
