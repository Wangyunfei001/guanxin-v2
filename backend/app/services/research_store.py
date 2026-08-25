"""SQLite repository for persistent Deep Research runs."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.core.sqlite import connect, initialize_database, transaction


ACTIVE_RESEARCH_STATUSES = {
    "planning",
    "searching",
    "analyzing",
    "synthesizing",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonicalize_url(value: str) -> str:
    """Normalize a public source URL for run-local deduplication."""
    value = value.strip()
    if not value:
        return ""
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return ""
    blocked = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "ref"}
    query = urlencode(
        sorted((key, val) for key, val in parse_qsl(parts.query) if key.lower() not in blocked)
    )
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def _json(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return fallback


class ResearchStore:
    """Own research lifecycle, tasks, sources and resumable event history."""

    def create_run(
        self,
        *,
        tenant_id: str,
        user_id: str,
        conversation_id: str,
        mode: str,
        goal: str,
        budget: dict[str, Any],
    ) -> dict:
        if mode not in {"quick", "deep"}:
            raise ValueError("research mode 必须是 quick 或 deep")
        initialize_database()
        run_id = f"research_{uuid.uuid4().hex}"
        now = _now()
        with transaction() as conn:
            conn.execute(
                """
                INSERT INTO research_runs(
                    run_id, tenant_id, user_id, conversation_id, mode, status,
                    goal, plan_json, budget_json, usage_json, report, error,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'planning', ?, '{}', ?, '{}', '', '', ?, ?)
                """,
                (
                    run_id,
                    tenant_id,
                    user_id,
                    conversation_id,
                    mode,
                    goal,
                    json.dumps(budget, ensure_ascii=False),
                    now,
                    now,
                ),
            )
        self.append_event(run_id, "created", {"mode": mode, "goal": goal})
        return self.get_run(run_id, tenant_id, user_id) or {}

    def get_run(
        self,
        run_id: str,
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> dict | None:
        initialize_database()
        clauses = ["run_id=?"]
        params: list[Any] = [run_id]
        if tenant_id is not None:
            clauses.append("tenant_id=?")
            params.append(tenant_id)
        if user_id is not None:
            clauses.append("user_id=?")
            params.append(user_id)
        conn = connect()
        try:
            row = conn.execute(
                f"SELECT * FROM research_runs WHERE {' AND '.join(clauses)}",
                params,
            ).fetchone()
            if row is None:
                return None
            run = dict(row)
            run["plan"] = _json(run.pop("plan_json"), {})
            run["budget"] = _json(run.pop("budget_json"), {})
            run["usage"] = _json(run.pop("usage_json"), {})
            run["tasks"] = [dict(item) for item in conn.execute(
                "SELECT * FROM research_tasks WHERE run_id=? ORDER BY position",
                (run_id,),
            ).fetchall()]
            run["sources"] = []
            for source_row in conn.execute(
                "SELECT * FROM research_sources WHERE run_id=? ORDER BY accessed_at",
                (run_id,),
            ).fetchall():
                source = dict(source_row)
                source["metadata"] = _json(source.pop("metadata_json"), {})
                run["sources"].append(source)
            run["events"] = []
            for event_row in conn.execute(
                "SELECT * FROM research_events WHERE run_id=? ORDER BY sequence",
                (run_id,),
            ).fetchall():
                event = dict(event_row)
                event["payload"] = _json(event.pop("payload_json"), {})
                run["events"].append(event)
            return run
        finally:
            conn.close()

    def set_plan(self, run_id: str, plan: dict[str, Any], questions: list[str]) -> None:
        initialize_database()
        now = _now()
        with transaction() as conn:
            conn.execute(
                "UPDATE research_runs SET plan_json=?, updated_at=? WHERE run_id=?",
                (json.dumps(plan, ensure_ascii=False), now, run_id),
            )
            for position, question in enumerate(questions):
                conn.execute(
                    """
                    INSERT OR IGNORE INTO research_tasks(
                        task_id, run_id, position, question, status,
                        attempt_count, result_summary, error, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, 'pending', 0, '', '', ?, ?)
                    """,
                    (f"task_{uuid.uuid4().hex}", run_id, position, question, now, now),
                )

    def add_tasks(self, run_id: str, questions: list[str]) -> int:
        """Append unique gap-analysis questions while preserving stable positions."""
        if not questions:
            return 0
        now = _now()
        inserted = 0
        with transaction() as conn:
            rows = conn.execute(
                "SELECT question FROM research_tasks WHERE run_id=?",
                (run_id,),
            ).fetchall()
            existing = {row["question"].strip() for row in rows}
            position = conn.execute(
                "SELECT COALESCE(MAX(position), -1) + 1 AS value FROM research_tasks WHERE run_id=?",
                (run_id,),
            ).fetchone()["value"]
            for question in questions:
                normalized = question.strip()
                if not normalized or normalized in existing:
                    continue
                conn.execute(
                    """
                    INSERT INTO research_tasks(
                        task_id, run_id, position, question, status,
                        attempt_count, result_summary, error, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, 'pending', 0, '', '', ?, ?)
                    """,
                    (f"task_{uuid.uuid4().hex}", run_id, position, normalized, now, now),
                )
                existing.add(normalized)
                position += 1
                inserted += 1
        return inserted

    def set_status(
        self,
        run_id: str,
        status: str,
        *,
        report: str | None = None,
        error: str | None = None,
        usage: dict[str, Any] | None = None,
    ) -> None:
        fields = ["status=?", "updated_at=?"]
        params: list[Any] = [status, _now()]
        if report is not None:
            fields.append("report=?")
            params.append(report)
        if error is not None:
            fields.append("error=?")
            params.append(error)
        if usage is not None:
            fields.append("usage_json=?")
            params.append(json.dumps(usage, ensure_ascii=False))
        params.append(run_id)
        with transaction() as conn:
            conn.execute(
                f"UPDATE research_runs SET {', '.join(fields)} WHERE run_id=?",
                params,
            )
        self.append_event(run_id, "status", {"status": status, "error": error or ""})

    def update_task(
        self,
        task_id: str,
        status: str,
        *,
        result_summary: str = "",
        error: str = "",
        increment_attempt: bool = False,
    ) -> None:
        attempt = ", attempt_count=attempt_count+1" if increment_attempt else ""
        with transaction() as conn:
            conn.execute(
                f"""
                UPDATE research_tasks
                SET status=?, result_summary=?, error=?, updated_at=?{attempt}
                WHERE task_id=?
                """,
                (status, result_summary, error, _now(), task_id),
            )

    def upsert_source(
        self,
        run_id: str,
        *,
        url: str,
        title: str = "",
        publisher: str = "",
        snippet: str = "",
        query: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict | None:
        canonical_url = canonicalize_url(url)
        if not canonical_url:
            return None
        now = _now()
        with transaction() as conn:
            conn.execute(
                """
                INSERT INTO research_sources(
                    source_id, run_id, canonical_url, title, publisher, snippet,
                    query, accessed_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, canonical_url) DO UPDATE SET
                    title=CASE WHEN excluded.title<>'' THEN excluded.title ELSE title END,
                    publisher=CASE WHEN excluded.publisher<>'' THEN excluded.publisher ELSE publisher END,
                    snippet=CASE WHEN excluded.snippet<>'' THEN excluded.snippet ELSE snippet END,
                    query=CASE WHEN excluded.query<>'' THEN excluded.query ELSE query END,
                    accessed_at=excluded.accessed_at,
                    metadata_json=excluded.metadata_json
                """,
                (
                    f"source_{uuid.uuid4().hex}",
                    run_id,
                    canonical_url,
                    title,
                    publisher,
                    snippet,
                    query,
                    now,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
        run = self.get_run(run_id)
        if run is None:
            return None
        return next(
            (source for source in run["sources"] if source["canonical_url"] == canonical_url),
            None,
        )

    def append_event(self, run_id: str, event_type: str, payload: dict[str, Any]) -> None:
        now = _now()
        with transaction() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(sequence), 0) AS value FROM research_events WHERE run_id=?",
                (run_id,),
            ).fetchone()
            sequence = int(row["value"]) + 1
            conn.execute(
                """
                INSERT INTO research_events(
                    event_id, run_id, sequence, event_type, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    f"event_{uuid.uuid4().hex}",
                    run_id,
                    sequence,
                    event_type,
                    json.dumps(payload, ensure_ascii=False),
                    now,
                ),
            )

    def cancel(self, run_id: str, tenant_id: str, user_id: str) -> dict | None:
        run = self.get_run(run_id, tenant_id, user_id)
        if run is None:
            return None
        if run["status"] in ACTIVE_RESEARCH_STATUSES | {"interrupted"}:
            self.set_status(run_id, "cancelled")
        return self.get_run(run_id, tenant_id, user_id)

    def recover_inflight(self) -> int:
        initialize_database()
        now = _now()
        placeholders = ",".join("?" for _ in ACTIVE_RESEARCH_STATUSES)
        with transaction() as conn:
            cursor = conn.execute(
                f"""
                UPDATE research_runs SET status='interrupted', updated_at=?
                WHERE status IN ({placeholders})
                """,
                (now, *sorted(ACTIVE_RESEARCH_STATUSES)),
            )
            return cursor.rowcount


_store: ResearchStore | None = None


def get_research_store() -> ResearchStore:
    global _store
    if _store is None:
        _store = ResearchStore()
    return _store
