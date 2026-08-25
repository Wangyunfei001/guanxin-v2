"""安全模块：JWT 令牌生成与校验、密码哈希。"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
from jose import JWTError, jwt

from app.config import settings

# bcrypt 算法只处理前 72 字节（与 passlib 旧行为一致，超出部分截断）
BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    """对明文密码进行哈希。"""
    return bcrypt.hashpw(
        password.encode("utf-8")[:BCRYPT_MAX_BYTES],
        bcrypt.gensalt(),
    ).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码与哈希值是否匹配。"""
    return bcrypt.checkpw(
        plain_password.encode("utf-8")[:BCRYPT_MAX_BYTES],
        hashed_password.encode("utf-8"),
    )


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """生成 JWT 访问令牌。

    Args:
        data: 要编码到 JWT 中的数据，必须包含 sub (用户ID)
        expires_delta: 过期时间增量，默认使用配置中的 jwt_expire_minutes

    Returns:
        JWT 令牌字符串
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """解码并验证 JWT 令牌。

    Args:
        token: JWT 令牌字符串

    Returns:
        解码后的 payload 字典，验证失败返回 None
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError:
        return None


def create_api_key(tenant_id: str, user_id: str) -> str:
    """生成 API Key（简单实现，用于 API Key 认证）。

    格式: gxin_{tenant_id}_{user_id}_{random}
    """
    import secrets

    random_part = secrets.token_hex(8)
    return f"gxin_{tenant_id}_{user_id}_{random_part}"
