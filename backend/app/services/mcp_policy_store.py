"""SQLite-backed tenant policies for discovered MCP tools."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.core.sqlite import connect, initialize_database, transaction


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decode(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    item = dict(row)
    item["enabled"] = bool(item["enabled"])
    item["approval_required"] = bool(item["approval_required"])
    item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
    return item


class MCPToolPolicyStore:
    """Persist tool-level enablement and risk classification per tenant."""

    def get(self, tenant_id: str, server_name: str, tool_name: str) -> dict | None:
        initialize_database()
        conn = connect()
        try:
            row = conn.execute(
                """
                SELECT * FROM mcp_tool_policies
                WHERE tenant_id=? AND server_name=? AND tool_name=?
                """,
                (tenant_id, server_name, tool_name),
            ).fetchone()
            return _decode(row)
        finally:
            conn.close()

    def list_for_tenant(self, tenant_id: str) -> list[dict]:
        initialize_database()
        conn = connect()
        try:
            rows = conn.execute(
                """
                SELECT * FROM mcp_tool_policies
                WHERE tenant_id=? ORDER BY server_name, tool_name
                """,
                (tenant_id,),
            ).fetchall()
            return [_decode(row) for row in rows]
        finally:
            conn.close()

    def ensure(
        self,
        tenant_id: str,
        server_name: str,
        tool_name: str,
        *,
        effect: str = "unknown",
        approval_required: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> dict:
        initialize_database()
        now = _now()
        with transaction() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO mcp_tool_policies(
                    tenant_id, server_name, tool_name, enabled, effect,
                    approval_required, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)
                """,
                (
                    tenant_id,
                    server_name,
                    tool_name,
                    effect,
                    int(approval_required),
                    json.dumps(metadata or {}, ensure_ascii=False),
                    now,
                    now,
                ),
            )
        return self.get(tenant_id, server_name, tool_name) or {}

    def save(
        self,
        tenant_id: str,
        server_name: str,
        tool_name: str,
        *,
        enabled: bool,
        effect: str,
        approval_required: bool,
        metadata: dict[str, Any] | None = None,
    ) -> dict:
        if effect not in {"read", "write", "unknown"}:
            raise ValueError("effect 必须是 read、write 或 unknown")
        initialize_database()
        now = _now()
        with transaction() as conn:
            conn.execute(
                """
                INSERT INTO mcp_tool_policies(
                    tenant_id, server_name, tool_name, enabled, effect,
                    approval_required, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, server_name, tool_name) DO UPDATE SET
                    enabled=excluded.enabled,
                    effect=excluded.effect,
                    approval_required=excluded.approval_required,
                    metadata_json=excluded.metadata_json,
                    updated_at=excluded.updated_at
                """,
                (
                    tenant_id,
                    server_name,
                    tool_name,
                    int(enabled),
                    effect,
                    int(approval_required),
                    json.dumps(metadata or {}, ensure_ascii=False),
                    now,
                    now,
                ),
            )
        return self.get(tenant_id, server_name, tool_name) or {}

    def delete_server(self, tenant_id: str, server_name: str) -> int:
        initialize_database()
        with transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM mcp_tool_policies WHERE tenant_id=? AND server_name=?",
                (tenant_id, server_name),
            )
            return cursor.rowcount


_store: MCPToolPolicyStore | None = None


def get_mcp_tool_policy_store() -> MCPToolPolicyStore:
    global _store
    if _store is None:
        _store = MCPToolPolicyStore()
    return _store
