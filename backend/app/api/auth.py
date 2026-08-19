"""认证 API 模块。

提供登录、获取用户信息、刷新令牌等接口。
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.deps import get_current_user, get_user_manager
from app.core.responses import success
from app.core.security import create_access_token
from app.models.tenant import User

router = APIRouter(prefix="/auth", tags=["认证"])


class LoginRequest(BaseModel):
    """登录请求模型。"""

    username: str
    password: str
    tenant_id: str = ""


class LoginResponse(BaseModel):
    """登录响应模型。"""

    access_token: str
    token_type: str = "bearer"
    user: dict


@router.post("/login")
async def login(request: LoginRequest):
    """用户登录。

    验证用户名密码，返回 JWT 令牌。
    """
    manager = get_user_manager()
    user = manager.authenticate(request.username, request.password, request.tenant_id)

    if user is None:
        return {
            "code": 4011,
            "message": "用户名或密码错误",
            "data": None,
        }

    token = create_access_token(
        {
            "sub": user.user_id,
            "tenant_id": user.tenant_id,
            "role": user.role,
            "username": user.username,
        }
    )

    return success(
        {
            "access_token": token,
            "token_type": "bearer",
            "user": user.to_dict(),
        }
    )


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    """获取当前登录用户信息。"""
    return success(user.to_dict())


@router.get("/api-keys")
async def list_api_keys(user: User = Depends(get_current_user)):
    """列出当前用户的 API Key。"""
    return success({"api_keys": user.api_keys})
