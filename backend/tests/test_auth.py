"""认证 API 测试。"""

import pytest


class TestAuth:
    """认证 API 测试套件。"""

    def test_login_success(self, test_client):
        """测试登录成功。"""
        response = test_client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "access_token" in data["data"]
        assert data["data"]["token_type"] == "bearer"
        assert data["data"]["user"]["username"] == "admin"
        assert data["data"]["user"]["role"] == "admin"

    def test_login_wrong_password(self, test_client):
        """测试密码错误登录失败。"""
        response = test_client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "wrong_password"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 4011
        assert "错误" in data["message"]

    def test_login_nonexistent_user(self, test_client):
        """测试不存在用户登录失败。"""
        response = test_client.post(
            "/api/auth/login",
            json={"username": "nonexistent", "password": "password"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 4011

    def test_protected_endpoint_without_token(self, test_client):
        """测试无令牌访问受保护接口。"""
        response = test_client.get("/api/auth/me")
        assert response.status_code == 401

    def test_protected_endpoint_with_token(self, test_client, admin_headers):
        """测试带令牌访问受保护接口。"""
        response = test_client.get("/api/auth/me", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["username"] == "admin"

    def test_me_returns_correct_tenant(self, test_client, demo_headers):
        """测试 /me 返回正确的租户信息。"""
        response = test_client.get("/api/auth/me", headers=demo_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["tenant_id"] == "tenant-b"

    def test_user_can_access_knowledge(self, test_client, user_headers):
        """测试普通用户可以访问知识库。"""
        response = test_client.get("/api/knowledge/documents", headers=user_headers)
        assert response.status_code == 200

    def test_api_key_authentication(self, test_client, admin_headers):
        """测试 API Key 认证。"""
        # 先获取 API Key
        response = test_client.get("/api/auth/api-keys", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]["api_keys"]) > 0

        api_key = data["data"]["api_keys"][0]

        # 使用 API Key 访问
        response = test_client.get(
            "/api/auth/me",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["username"] == "admin"
