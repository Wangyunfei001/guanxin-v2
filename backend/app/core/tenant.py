"""多租户上下文管理模块。

使用 contextvars 实现请求级别的租户隔离，
确保每个请求只能访问自己租户的数据。
"""

import contextvars
from typing import Optional

# 租户 ID 上下文变量
_tenant_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "tenant_id", default=None
)

# 用户 ID 上下文变量
_user_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "user_id", default=None
)

# 用户角色上下文变量
_user_role_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "user_role", default=None
)


def set_tenant_context(tenant_id: str, user_id: str, user_role: str) -> None:
    """设置当前请求的租户上下文。"""
    _tenant_id_ctx.set(tenant_id)
    _user_id_ctx.set(user_id)
    _user_role_ctx.set(user_role)


def get_tenant_id() -> Optional[str]:
    """获取当前租户 ID。"""
    return _tenant_id_ctx.get()


def get_user_id() -> Optional[str]:
    """获取当前用户 ID。"""
    return _user_id_ctx.get()


def get_user_role() -> Optional[str]:
    """获取当前用户角色。"""
    return _user_role_ctx.get()


def clear_tenant_context() -> None:
    """清除租户上下文。"""
    _tenant_id_ctx.set(None)
    _user_id_ctx.set(None)
    _user_role_ctx.set(None)


def get_kb_collection_name(tenant_id: Optional[str] = None) -> str:
    """根据租户 ID 生成知识库集合名称。

    Args:
        tenant_id: 租户 ID，若为空则从上下文获取

    Returns:
        ChromaDB 集合名称，格式: tenant-{id}-kb
    """
    tid = tenant_id or get_tenant_id()
    if not tid:
        raise ValueError("无法确定租户 ID，请先设置租户上下文")
    return f"tenant-{tid}-kb"
