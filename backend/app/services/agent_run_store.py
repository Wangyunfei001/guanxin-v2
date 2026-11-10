"""Durable delivery log for the official LangChain thread HTTP protocol.

Checkpoints remain the execution state. This store owns only run admission,
delivery/replay and outcome; it never reconstructs the agent's tool loop.

写入在工作线程执行。v3 协议下**每个模型 chunk 都会产生一个事件**，如果
同步提交，整条写事务都发生在事件循环里——同一进程上所有会话的流都会被
拖慢。复用 ``app.core.sqlite`` 的既有纪律（WAL、busy_timeout、
BEGIN IMMEDIATE、外键），只是把提交挪出事件循环。

事件写入只做**一条 INSERT**：``seq`` 与 ``event_id`` 在读取时补齐，因此
不需要先插空行再回填 payload 的两步写。
"""
from __future__ import annotations

import asyncio
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


def protocol_event(method: str, data: Any) -> dict:
    return {"type": "event", "method": method,
            "params": {"namespace": [], "timestamp": int(time.time() * 1000), "data": data}}


def _latest_run_sync(conversation_id: str) -> dict | None:
    with closing(connect()) as db:
        row = db.execute(
            "SELECT * FROM agent_runs WHERE conversation_id=? ORDER BY created_at DESC LIMIT 1",
            (conversation_id,),
        ).fetchone()
        return dict(row) if row else None


async def latest_run(conversation_id: str) -> dict | None:
    """最近一次运行；读取在工作线程执行。"""
    return await asyncio.to_thread(_latest_run_sync, conversation_id)


def _admit_run_sync(conversation_id: str, request_key: str) -> tuple[dict, bool]:
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


async def admit_run(conversation_id: str, request_key: str) -> tuple[dict, bool]:
    """准入一次运行；同一会话至多一个 running。"""
    return await asyncio.to_thread(_admit_run_sync, conversation_id, request_key)


def _insert_event_sync(conversation_id: str, run_id: str, payload: str) -> None:
    with transaction() as db:
        db.execute(
            "INSERT INTO agent_events(conversation_id,run_id,payload) VALUES (?,?,?)",
            (conversation_id, run_id, payload),
        )


async def append_event(run: dict, event: dict[str, Any]) -> None:
    """持久化一个事件。

    ``seq`` 与 ``event_id`` 在读取时补齐——写入因此只有一条 INSERT，
    而不是先插空行再 UPDATE 回填 payload 的两步写。
    """
    payload = json.dumps({**event, "type": "event"}, ensure_ascii=False)
    await asyncio.to_thread(
        _insert_event_sync, run["conversation_id"], run["run_id"], payload
    )


def _finish_run_sync(run: dict, status: str, error: str) -> None:
    with transaction() as db:
        db.execute("UPDATE agent_runs SET status=?,error=? WHERE run_id=?",
                   (status, error, run["run_id"]))
    phase = "interrupted" if status in {"cancelled", "interrupted", "waiting_approval"} else status
    data = {"event": phase}
    if error:
        data["error"] = error
    payload = json.dumps(
        {**protocol_event("lifecycle", data), "type": "event"}, ensure_ascii=False
    )
    _insert_event_sync(run["conversation_id"], run["run_id"], payload)


async def finish_run(run: dict, status: str, error: str = "") -> None:
    """结束一次运行并追加终止事件。"""
    await asyncio.to_thread(_finish_run_sync, run, status, error)


def _running_runs_sync() -> list[Any]:
    with closing(connect()) as db:
        return db.execute("SELECT * FROM agent_runs WHERE status='running'").fetchall()


async def recover_agent_runs() -> None:
    """把重启前遗留的 running 标记为 interrupted。"""
    rows = await asyncio.to_thread(_running_runs_sync)
    for row in rows:
        await finish_run(
            dict(row), "interrupted", "服务重启，任务已中断；请确认后继续。"
        )


def _read_events_sync(conversation_id: str, since: int) -> list[tuple[int, str, str]]:
    with closing(connect()) as db:
        rows = db.execute(
            "SELECT seq,run_id,payload FROM agent_events WHERE conversation_id=? AND seq>? ORDER BY seq LIMIT 256",
            (conversation_id, since),
        ).fetchall()
    return [(row[0], row[1], row[2]) for row in rows]


async def read_events(conversation_id: str, since: int) -> list[dict]:
    """按 ``seq`` 游标读取可重放事件。"""
    rows = await asyncio.to_thread(_read_events_sync, conversation_id, since)
    events: list[dict] = []
    for seq, run_id, payload in rows:
        events.append({**json.loads(payload), "seq": seq, "event_id": f"{run_id}:{seq}"})
    return events
