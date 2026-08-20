"""pytest 配置与 fixtures。"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from typing import Generator

import pytest

# 确保后端包可导入
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# 设置测试环境变量
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ["EMBEDDING_PROVIDER"] = "openai"
os.environ["EMBEDDING_API_KEY"] = ""
os.environ.setdefault("CHROMA_PERSIST_DIR", tempfile.mkdtemp(prefix="chroma_test_"))
os.environ.setdefault("UPLOAD_DIR", tempfile.mkdtemp(prefix="uploads_test_"))
os.environ.setdefault(
    "DATABASE_PATH",
    str(Path(tempfile.mkdtemp(prefix="sqlite_test_")) / "guanxin-test.db"),
)


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环。"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_client():
    """创建测试客户端。"""
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app()
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="session")
def admin_token(test_client) -> str:
    """获取管理员 JWT 令牌。"""
    response = test_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    data = response.json()
    return data["data"]["access_token"]


@pytest.fixture(scope="session")
def user_token(test_client) -> str:
    """获取普通用户 JWT 令牌。"""
    response = test_client.post(
        "/api/auth/login",
        json={"username": "user", "password": "user123"},
    )
    data = response.json()
    return data["data"]["access_token"]


@pytest.fixture(scope="session")
def demo_token(test_client) -> str:
    """获取 Demo 用户 JWT 令牌（租户B）。"""
    response = test_client.post(
        "/api/auth/login",
        json={"username": "demo", "password": "demo123"},
    )
    data = response.json()
    return data["data"]["access_token"]


@pytest.fixture(scope="session")
def admin_headers(admin_token) -> dict:
    """管理员请求头。"""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def user_headers(user_token) -> dict:
    """普通用户请求头。"""
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture(scope="session")
def demo_headers(demo_token) -> dict:
    """Demo 用户请求头（租户B）。"""
    return {"Authorization": f"Bearer {demo_token}"}
