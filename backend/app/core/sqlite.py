"""SQLite 业务数据库基础设施。"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from app.config import settings

SCHEMA_VERSION = 2


def _database_path() -> Path:
    return settings.business_database_path


def connect() -> sqlite3.Connection:
    """创建配置一致的 SQLite 连接。"""
    conn = sqlite3.connect(
        str(_database_path()),
        timeout=5.0,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """提供自动提交/回滚的事务连接。"""
    conn = connect()
    try:
        # Acquire the write reservation up front so concurrent writers wait on
        # busy_timeout instead of failing while upgrading a deferred read txn.
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_database() -> None:
    """幂等初始化当前版本数据库结构。"""
    with transaction() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS documents (
                doc_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_type TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                chunk_count INTEGER NOT NULL DEFAULT 0,
                error_message TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_documents_tenant
                ON documents(tenant_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS document_chunks (
                chunk_id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
                tenant_id TEXT NOT NULL,
                content TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_chunks_document
                ON document_chunks(doc_id, chunk_index);

            CREATE TABLE IF NOT EXISTS conversations (
                conversation_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_conversations_owner
                ON conversations(tenant_id, user_id, updated_at DESC);

            CREATE TABLE IF NOT EXISTS conversation_messages (
                message_id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                tool_calls_json TEXT NOT NULL DEFAULT '[]',
                tool_call_id TEXT NOT NULL DEFAULT '',
                reasoning TEXT NOT NULL DEFAULT '',
                a2ui_schemas_json TEXT NOT NULL DEFAULT '[]',
                parts_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_messages_conversation
                ON conversation_messages(conversation_id, created_at);

            CREATE TABLE IF NOT EXISTS agent_configs (
                tenant_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL,
                system_prompt TEXT NOT NULL DEFAULT '',
                temperature REAL NOT NULL,
                max_tokens INTEGER NOT NULL,
                enabled_tools_json TEXT NOT NULL DEFAULT '[]',
                enabled_skills_json TEXT NOT NULL DEFAULT '[]',
                mcp_servers_json TEXT NOT NULL DEFAULT '[]',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, agent_id)
            );

            CREATE TABLE IF NOT EXISTS tool_approvals (
                approval_id TEXT PRIMARY KEY,
                tool_call_id TEXT NOT NULL,
                conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
                action_json TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected','consumed')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_approvals_conversation
                ON tool_approvals(conversation_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS workflow_runs (
                run_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
                agent_id TEXT NOT NULL,
                goal TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                plan_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL CHECK(status IN (
                    'planning','running','waiting_input','waiting_approval',
                    'uncertain','completed','failed','cancelled'
                )),
                current_step_index INTEGER NOT NULL DEFAULT 0,
                checkpoint_thread_id TEXT NOT NULL UNIQUE,
                version INTEGER NOT NULL DEFAULT 1,
                last_error TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_workflow_runs_owner
                ON workflow_runs(tenant_id, user_id, updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_workflow_runs_conversation
                ON workflow_runs(conversation_id, updated_at DESC);
            CREATE UNIQUE INDEX IF NOT EXISTS uq_workflow_active_conversation
                ON workflow_runs(conversation_id)
                WHERE status IN (
                    'planning','running','waiting_input','waiting_approval','uncertain'
                );

            CREATE TABLE IF NOT EXISTS workflow_steps (
                step_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES workflow_runs(run_id) ON DELETE CASCADE,
                position INTEGER NOT NULL,
                title TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                tool_category TEXT NOT NULL,
                args_json TEXT NOT NULL DEFAULT '{}',
                resolved_args_json TEXT NOT NULL DEFAULT '{}',
                risk TEXT NOT NULL CHECK(risk IN ('read','write','unknown')),
                status TEXT NOT NULL CHECK(status IN (
                    'pending','waiting_input','waiting_approval','executing',
                    'completed','failed','uncertain','cancelled'
                )),
                attempt_count INTEGER NOT NULL DEFAULT 0,
                idempotency_key TEXT NOT NULL UNIQUE,
                result_json TEXT NOT NULL DEFAULT 'null',
                error TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(run_id, position)
            );
            CREATE INDEX IF NOT EXISTS idx_workflow_steps_run
                ON workflow_steps(run_id, position);

            CREATE TABLE IF NOT EXISTS workflow_interrupts (
                interrupt_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES workflow_runs(run_id) ON DELETE CASCADE,
                step_id TEXT NOT NULL REFERENCES workflow_steps(step_id) ON DELETE CASCADE,
                kind TEXT NOT NULL CHECK(kind IN ('input','approval','recovery')),
                status TEXT NOT NULL CHECK(status IN ('pending','resolved','rejected','cancelled')),
                payload_json TEXT NOT NULL DEFAULT '{}',
                response_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_workflow_interrupts_run
                ON workflow_interrupts(run_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS workflow_step_executions (
                execution_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES workflow_runs(run_id) ON DELETE CASCADE,
                step_id TEXT NOT NULL REFERENCES workflow_steps(step_id) ON DELETE CASCADE,
                attempt INTEGER NOT NULL,
                idempotency_key TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL CHECK(status IN ('executing','completed','failed','uncertain')),
                result_json TEXT NOT NULL DEFAULT 'null',
                error TEXT NOT NULL DEFAULT '',
                started_at TEXT NOT NULL,
                completed_at TEXT,
                UNIQUE(run_id, step_id, attempt)
            );
            """
        )
        conn.execute(
            "INSERT OR IGNORE INTO schema_version(version, applied_at) VALUES (?, datetime('now'))",
            (SCHEMA_VERSION,),
        )


def close_database() -> None:
    """兼容生命周期接口；当前实现不持有长连接。"""


def reset_database_for_tests(path: Optional[Path] = None) -> None:
    """删除测试数据库及 WAL sidecar。仅供测试使用。"""
    db_path = path or _database_path()
    for candidate in (
        db_path,
        Path(f"{db_path}-wal"),
        Path(f"{db_path}-shm"),
    ):
        candidate.unlink(missing_ok=True)
