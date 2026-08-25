"""UI-facing workflow snapshots and stable message identities."""

from __future__ import annotations

from typing import Any, Optional


def workflow_message_id(run_id: str) -> str:
    """Return the one assistant message ID owned by a workflow run."""
    return f"workflow-msg-{run_id}"


def workflow_public_data(run: dict[str, Any]) -> dict[str, Any]:
    """Return the UI-safe workflow snapshot used by streams and polling."""
    steps = [
        {
            "step_id": step["step_id"],
            "position": step["position"],
            "title": step["title"],
            "tool_name": step["tool_name"],
            "category": step["tool_category"],
            "tool_category": step["tool_category"],
            "risk": step["risk"],
            "status": step["status"],
            "attempt_count": step["attempt_count"],
            "result": step["result"],
            "error": step["error"],
        }
        for step in run["steps"]
    ]
    pending = next(
        (item for item in reversed(run["interrupts"]) if item["status"] == "pending"),
        None,
    )
    return {
        "run_id": run["run_id"],
        "conversation_id": run["conversation_id"],
        "agent_id": run["agent_id"],
        "goal": run["goal"],
        "summary": run["summary"],
        "status": run["status"],
        "current_step_index": run["current_step_index"],
        "version": run["version"],
        "last_error": run["last_error"],
        "steps": steps,
        "pending_interrupt": (
            {
                "interrupt_id": pending["interrupt_id"],
                "kind": pending["kind"],
                "payload": pending["payload"],
            }
            if pending
            else None
        ),
        "interrupts": [
            {
                key: item[key]
                for key in (
                    "interrupt_id",
                    "step_id",
                    "kind",
                    "status",
                    "payload",
                    "created_at",
                    "updated_at",
                )
            }
            for item in run["interrupts"]
        ],
        "created_at": run["created_at"],
        "updated_at": run["updated_at"],
    }


def pending_workflow_part(run: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Return the one actionable AI SDK tool part for a workflow run."""
    pending = next(
        (item for item in reversed(run["interrupts"]) if item["status"] == "pending"),
        None,
    )
    if pending is None or pending["kind"] not in {"input", "approval"}:
        return None
    tool_call_id = f"workflow_{pending['interrupt_id']}"
    return {
        "type": "tool-workflow_control",
        "toolCallId": tool_call_id,
        "state": "approval-requested",
        "input": {
            "run_id": run["run_id"],
            "interrupt_id": pending["interrupt_id"],
            "kind": pending["kind"],
            **pending["payload"],
        },
        "approval": {"id": pending["interrupt_id"]},
    }
