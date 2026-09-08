"""Durable delivery log for the official LangChain thread HTTP protocol.

Checkpoints remain the execution state. This store owns only run admission,
delivery/replay and outcome; it never reconstructs the agent's tool loop.
"""
from __future__ import annotations

import json
import time
import uuid
from contextlib import closing
from typing import Any

from app.core.sqlite import connect, transaction


def initialize_agent_runs() -> None:
    with transaction() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS agent_runs (
            run_id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL
              REFERENCES conversations(conversation_id) ON DELETE CASCADE,
            request_key TEXT NOT NULL, status TEXT NOT NULL, error TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL, UNIQUE(conversation_id, request_key))""")
        db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS one_active_agent_run
            ON agent_runs(conversation_id) WHERE status='running'""")
        db.execute("""CREATE TABLE IF NOT EXISTS agent_events (
            seq INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL
              REFERENCES conversations(conversation_id) ON DELETE CASCADE,
            run_id TEXT NOT NULL REFERENCES agent_runs(run_id) ON DELETE CASCADE,
            payload TEXT NOT NULL)""")
        db.execute("CREATE INDEX IF NOT EXISTS agent_events_thread ON agent_events(conversation_id,seq)")


def latest_run(conversation_id: str) -> dict | None:
    with closing(connect()) as db:
        row = db.execute("SELECT * FROM agent_runs WHERE conversation_id=? ORDER BY created_at DESC LIMIT 1",
                         (conversation_id,)).fetchone()
        return dict(row) if row else None


def admit_run(conversation_id: str, request_key: str) -> tuple[dict, bool]:
    with transaction() as db:
        row = db.execute("SELECT * FROM agent_runs WHERE conversation_id=? AND request_key=?",
                         (conversation_id, request_key)).fetchone()
        if row:
            return dict(row), False
        if db.execute("SELECT 1 FROM agent_runs WHERE conversation_id=? AND status='running'",
                      (conversation_id,)).fetchone():
            raise ValueError("当前会话已有任务运行中")
        run = dict(run_id=str(uuid.uuid4()), conversation_id=conversation_id,
                   request_key=request_key, status="running", error="", created_at=time.time())
        db.execute("INSERT INTO agent_runs VALUES (:run_id,:conversation_id,:request_key,:status,:error,:created_at)", run)
        return run, True


def append_event(run: dict, event: dict[str, Any]) -> None:
    with transaction() as db:
        cursor = db.execute("INSERT INTO agent_events(conversation_id,run_id,payload) VALUES (?,?,?)",
                            (run["conversation_id"], run["run_id"], ""))
        seq = cursor.lastrowid
        event = {**event, "type": "event", "seq": seq, "event_id": f"{run['run_id']}:{seq}"}
        db.execute("UPDATE agent_events SET payload=? WHERE seq=?",
                   (json.dumps(event, ensure_ascii=False), seq))


def protocol_event(method: str, data: Any) -> dict:
    return {"type": "event", "method": method,
            "params": {"namespace": [], "timestamp": int(time.time() * 1000), "data": data}}


def finish_run(run: dict, status: str, error: str = "") -> None:
    with transaction() as db:
        db.execute("UPDATE agent_runs SET status=?,error=? WHERE run_id=?",
                   (status, error, run["run_id"]))
    phase = "interrupted" if status in {"cancelled", "interrupted", "waiting_approval"} else status
    data = {"event": phase}
    if error:
        data["error"] = error
    append_event(run, protocol_event("lifecycle", data))


def recover_agent_runs() -> None:
    with closing(connect()) as db:
        rows = db.execute("SELECT * FROM agent_runs WHERE status='running'").fetchall()
    for row in rows:
        finish_run(dict(row), "interrupted", "服务重启，任务已中断；请确认后继续。")


def read_events(conversation_id: str, since: int) -> list[dict]:
    with closing(connect()) as db:
        rows = db.execute("SELECT payload FROM agent_events WHERE conversation_id=? AND seq>? ORDER BY seq LIMIT 256",
                          (conversation_id, since)).fetchall()
    return [json.loads(row[0]) for row in rows]
