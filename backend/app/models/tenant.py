"""租户与用户模型模块。

使用内存存储管理租户和用户数据，
支持 JWT + API Key 双认证。
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.core.security import create_api_key, hash_password, verify_password


@dataclass
class User:
    """用户模型。"""

    user_id: str
    username: str
    password_hash: str
    tenant_id: str
    tenant_name: str
    role: str  # admin | user
    display_name: str = ""
    api_keys: List[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        """转换为字典（不包含敏感信息）。"""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "tenant_id": self.tenant_id,
            "tenant_name": self.tenant_name,
            "role": self.role,
            "display_name": self.display_name,
            "created_at": self.created_at,
        }


@dataclass
class Tenant:
    """租户模型。"""

    tenant_id: str
    name: str
    description: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# 预设用户配置
PRESET_USERS_CONFIG = [
    {
        "user_id": "admin-001",
        "username": "admin",
        "password": "admin123",
        "tenant_id": "tenant-a",
        "tenant_name": "演示租户 A",
        "role": "admin",
        "display_name": "管理员",
    },
    {
        "user_id": "user-001",
        "username": "user",
        "password": "user123",
        "tenant_id": "tenant-a",
        "tenant_name": "演示租户 A",
        "role": "user",
        "display_name": "普通用户",
    },
    {
        "user_id": "demo-001",
        "username": "demo",
        "password": "demo123",
        "tenant_id": "tenant-b",
        "tenant_name": "演示租户 B",
        "role": "admin",
        "display_name": "Demo 用户",
    },
]


class UserManager:
    """用户管理器：内存存储，管理用户和 API Key。"""

    def __init__(self) -> None:
        self._users: Dict[str, User] = {}  # key: "{tenant_id}:{username}"
        self._api_key_index: Dict[str, User] = {}  # key: api_key -> User
        self._initialized: bool = False

    def init_preset_users(self) -> None:
        """初始化预设用户（幂等）。"""
        if self._initialized:
            return
        for cfg in PRESET_USERS_CONFIG:
            self._create_user(
                user_id=cfg["user_id"],
                username=cfg["username"],
                password=cfg["password"],
                tenant_id=cfg["tenant_id"],
                tenant_name=cfg["tenant_name"],
                role=cfg["role"],
                display_name=cfg["display_name"],
                generate_api_key=True,
            )
        self._initialized = True

    def _create_user(
        self,
        user_id: str,
        username: str,
        password: str,
        tenant_id: str,
        tenant_name: str,
        role: str,
        display_name: str = "",
        generate_api_key: bool = False,
    ) -> User:
        """创建用户。"""
        key = f"{tenant_id}:{username}"
        if key in self._users:
            return self._users[key]

        user = User(
            user_id=user_id,
            username=username,
            password_hash=hash_password(password),
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            role=role,
            display_name=display_name or username,
        )

        if generate_api_key:
            api_key = create_api_key(tenant_id, user_id)
            user.api_keys.append(api_key)
            self._api_key_index[api_key] = user

        self._users[key] = user
        return user

    def authenticate(self, username: str, password: str, tenant_id: str = "") -> Optional[User]:
        """用户名密码认证。

        Args:
            username: 用户名
            password: 明文密码
            tenant_id: 可选租户 ID，为空则搜索所有租户

        Returns:
            匹配的用户对象，未找到返回 None
        """
        if tenant_id:
            key = f"{tenant_id}:{username}"
            user = self._users.get(key)
            if user and verify_password(password, user.password_hash):
                return user
        else:
            for key, user in self._users.items():
                if key.endswith(f":{username}") and verify_password(
                    password, user.password_hash
                ):
                    return user
        return None

    def get_user(self, user_id: str, tenant_id: str) -> Optional[User]:
        """根据用户 ID 和租户 ID 获取用户。"""
        for key, user in self._users.items():
            if user.user_id == user_id and user.tenant_id == tenant_id:
                return user
        return None

    def get_user_by_api_key(self, api_key: str) -> Optional[User]:
        """根据 API Key 获取用户。"""
        return self._api_key_index.get(api_key)

    def list_users(self, tenant_id: Optional[str] = None) -> List[User]:
        """列出用户。"""
        if tenant_id:
            return [u for u in self._users.values() if u.tenant_id == tenant_id]
        return list(self._users.values())
