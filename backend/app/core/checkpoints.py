"""Lifecycle-managed LangGraph SQLite checkpointer."""

from __future__ import annotations

import os
import asyncio
from contextlib import AbstractAsyncContextManager
from typing import Optional

from app.config import settings

os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver  # noqa: E402


_initialization_lock = asyncio.Lock()

_manager: Optional[AbstractAsyncContextManager[AsyncSqliteSaver]] = None
_checkpointer: Optional[AsyncSqliteSaver] = None


async def initialize_checkpointer() -> AsyncSqliteSaver:
    """Open the shared async SQLite saver and initialize its schema."""
    global _manager, _checkpointer
    async with _initialization_lock:
        if _checkpointer is not None:
            return _checkpointer
        manager = AsyncSqliteSaver.from_conn_string(str(settings.checkpoint_path))
        saver = await manager.__aenter__()
        await saver.setup()
        _manager = manager
        _checkpointer = saver
        return saver


def get_checkpointer() -> AsyncSqliteSaver:
    if _checkpointer is None:
        raise RuntimeError("LangGraph checkpointer 尚未初始化")
    return _checkpointer


async def delete_checkpoint_thread(thread_id: str) -> None:
    if _checkpointer is not None:
        await _checkpointer.adelete_thread(thread_id)


async def close_checkpointer() -> None:
    global _manager, _checkpointer
    manager = _manager
    _manager = None
    _checkpointer = None
    if manager is not None:
        await manager.__aexit__(None, None, None)
    try:
        from app.workflows.engine import reset_workflow_graph

        reset_workflow_graph()
    except ImportError:
        pass
