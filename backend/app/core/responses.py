"""统一响应模型模块。"""

from typing import Any, Optional

from pydantic import BaseModel


class ApiResponse(BaseModel):
    """统一 API 响应模型。"""

    code: int = 0
    message: str = "success"
    data: Optional[Any] = None


def success(data: Any = None, message: str = "success") -> dict:
    """构造成功响应。"""
    return {"code": 0, "message": message, "data": data}


def error(message: str = "error", code: int = -1, data: Any = None) -> dict:
    """构造错误响应。"""
    return {"code": code, "message": message, "data": data}
