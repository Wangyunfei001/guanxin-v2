"""Read-only projection for archived research records."""
from typing import Any

def public_research_snapshot(run: dict[str, Any]) -> dict[str, Any]:
    return {
        key: run[key]
        for key in (
            "run_id",
            "conversation_id",
            "mode",
            "status",
            "goal",
            "plan",
            "budget",
            "usage",
            "report",
            "error",
            "tasks",
            "sources",
            "created_at",
            "updated_at",
        )
        if key in run
    }
