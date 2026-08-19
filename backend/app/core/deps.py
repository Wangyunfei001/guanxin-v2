"""依赖注入模块：JWT 认证、API Key 认证、权限校验。"""

from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token
from app.core.tenant import set_tenant_context
from app.models.tenant import User, UserManager

# Bearer Token 安全方案
bearer_scheme = HTTPBearer(auto_error=False)

# 预设用户管理器
_user_manager: Optional[UserManager] = None


def get_user_manager() -> UserManager:
    """获取全局 UserManager 单例。"""
    global _user_manager
    if _user_manager is None:
        _user_manager = UserManager()
    return _user_manager


def init_preset_users() -> None:
    """初始化预设用户。"""
    manager = get_user_manager()
    manager.init_preset_users()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> User:
    """获取当前认证用户。

    支持两种认证方式：
    1. Bearer Token (JWT)
    2. X-API-Key

    Returns:
        当前用户对象

    Raises:
        HTTPException: 认证失败
    """
    user: Optional[User] = None

    # 尝试 JWT 认证
    if credentials and credentials.credentials:
        payload = decode_access_token(credentials.credentials)
        if payload:
            user_id = payload.get("sub")
            tenant_id = payload.get("tenant_id")
            if user_id and tenant_id:
                manager = get_user_manager()
                user = manager.get_user(user_id, tenant_id)

    # 尝试 API Key 认证
    if user is None and x_api_key:
        manager = get_user_manager()
        user = manager.get_user_by_api_key(x_api_key)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证失败：请提供有效的 Bearer Token 或 API Key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 设置租户上下文
    set_tenant_context(
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        user_role=user.role,
    )

    return user


async def get_admin_user(user: User = Depends(get_current_user)) -> User:
    """要求当前用户具有 admin 角色。

    Raises:
        HTTPException: 权限不足
    """
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足：需要管理员权限",
        )
    return user


def reset_user_manager() -> None:
    """重置 UserManager（用于测试）。"""
    global _user_manager
    _user_manager = None
