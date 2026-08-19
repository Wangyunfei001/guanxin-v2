"""User data store — simple JSON file persistence for demo purposes."""

import json
import os
import threading
from datetime import datetime, timezone
from typing import Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
DATA_FILE = os.path.join(DATA_DIR, "users.json")
_lock = threading.Lock()

# Seed users
_DEFAULT_USERS = [
    {
        "user_id": "usr_10001",
        "username": "张三",
        "email": "zhangsan@example.com",
        "role": "admin",
        "status": "active",
        "created_at": "2025-01-15T08:30:00+00:00",
    },
    {
        "user_id": "usr_10002",
        "username": "李四",
        "email": "lisi@example.com",
        "role": "user",
        "status": "active",
        "created_at": "2025-03-22T14:20:00+00:00",
    },
    {
        "user_id": "usr_10003",
        "username": "王五",
        "email": "wangwu@example.com",
        "role": "viewer",
        "status": "inactive",
        "created_at": "2025-06-10T09:45:00+00:00",
    },
]


def _load() -> list[dict]:
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        _save(_DEFAULT_USERS)
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return list(_DEFAULT_USERS)


def _save(users: list[dict]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def create_user(username: str, email: str, role: str = "user") -> dict:
    with _lock:
        users = _load()
        user_id = f"usr_{10000 + len(users) + 1}"
        now = datetime.now(timezone.utc).isoformat()
        user = {
            "user_id": user_id,
            "username": username,
            "email": email,
            "role": role,
            "status": "active",
            "created_at": now,
        }
        users.append(user)
        _save(users)
        return user


def query_users(keyword: str = "", role: str = "", page: int = 1, page_size: int = 10) -> dict:
    users = _load()
    if keyword:
        users = [u for u in users if keyword.lower() in u["username"].lower() or keyword.lower() in u["email"].lower()]
    if role:
        users = [u for u in users if u["role"] == role]
    total = len(users)
    start = (page - 1) * page_size
    page_users = users[start : start + page_size]
    return {
        "users": page_users,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def update_user(user_id: str, **fields) -> Optional[dict]:
    with _lock:
        users = _load()
        for u in users:
            if u["user_id"] == user_id:
                for k, v in fields.items():
                    if v is not None and v != "":
                        u[k] = v
                _save(users)
                return u
    return None


def delete_user(user_id: str) -> bool:
    with _lock:
        users = _load()
        for i, u in enumerate(users):
            if u["user_id"] == user_id:
                users.pop(i)
                _save(users)
                return True
    return False


def get_all_users() -> list[dict]:
    return _load()