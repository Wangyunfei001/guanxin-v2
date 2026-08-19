"""Agent API 测试。

测试对话管理（CRUD）和认证控制。
SSE 流式聊天测试较复杂，P0 阶段只测会话 CRUD 和配置管理。
"""

import pytest


class TestAgentConversation:
    """Agent 对话管理测试套件。"""

    def test_conversation_create(self, test_client, admin_headers):
        """测试创建对话。"""
        response = test_client.post(
            "/api/agent/conversations",
            headers=admin_headers,
            json={"agent_id": "default", "title": "测试对话"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "conversation_id" in data["data"]
        assert data["data"]["agent_id"] == "default"
        assert data["data"]["title"] == "测试对话"
        assert data["data"]["messages"] == []

    def test_conversation_create_default_title(self, test_client, admin_headers):
        """测试创建对话时使用默认标题。"""
        response = test_client.post(
            "/api/agent/conversations",
            headers=admin_headers,
            json={"agent_id": "default"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["title"] == "新对话"

    def test_conversation_list(self, test_client, admin_headers):
        """测试列出对话。"""
        # 先创建一个对话
        create_resp = test_client.post(
            "/api/agent/conversations",
            headers=admin_headers,
            json={"agent_id": "default", "title": "列表测试"},
        )
        conv_id = create_resp.json()["data"]["conversation_id"]

        # 列出对话
        response = test_client.get(
            "/api/agent/conversations",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert isinstance(data["data"], list)
        assert len(data["data"]) > 0

        # 验证返回的字段
        conv = data["data"][0]
        assert "conversation_id" in conv
        assert "title" in conv
        assert "agent_id" in conv
        assert "created_at" in conv
        assert "updated_at" in conv
        assert "message_count" in conv

    def test_conversation_get_detail(self, test_client, admin_headers):
        """测试获取对话详情。"""
        # 创建对话
        create_resp = test_client.post(
            "/api/agent/conversations",
            headers=admin_headers,
            json={"agent_id": "default", "title": "详情测试"},
        )
        conv_id = create_resp.json()["data"]["conversation_id"]

        # 获取详情
        response = test_client.get(
            f"/api/agent/conversations/{conv_id}",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["conversation_id"] == conv_id
        assert data["data"]["title"] == "详情测试"

    def test_conversation_get_nonexistent(self, test_client, admin_headers):
        """测试获取不存在的对话。"""
        response = test_client.get(
            "/api/agent/conversations/nonexistent-conv-id",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 4041
        assert "未找到" in data["message"]

    def test_conversation_delete(self, test_client, admin_headers):
        """测试删除对话。"""
        # 创建对话
        create_resp = test_client.post(
            "/api/agent/conversations",
            headers=admin_headers,
            json={"agent_id": "default", "title": "删除测试"},
        )
        conv_id = create_resp.json()["data"]["conversation_id"]

        # 删除
        response = test_client.delete(
            f"/api/agent/conversations/{conv_id}",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["deleted"] is True

        # 确认已删除
        get_resp = test_client.get(
            f"/api/agent/conversations/{conv_id}",
            headers=admin_headers,
        )
        assert get_resp.json()["code"] == 4041

    def test_conversation_delete_nonexistent(self, test_client, admin_headers):
        """测试删除不存在的对话。"""
        response = test_client.delete(
            "/api/agent/conversations/nonexistent-conv-id",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 4041

    def test_chat_unauthorized(self, test_client):
        """测试未认证不能聊天。"""
        response = test_client.post(
            "/api/agent/chat",
            json={
                "conversation_id": "any-conv-id",
                "message": "你好",
            },
        )
        assert response.status_code == 401

    def test_conversations_unauthorized(self, test_client):
        """测试未认证不能访问对话列表。"""
        response = test_client.get("/api/agent/conversations")
        assert response.status_code == 401

    def test_conversation_tenant_isolation(self, test_client, admin_headers, demo_headers):
        """测试对话租户隔离。"""
        # 租户A创建对话
        create_a = test_client.post(
            "/api/agent/conversations",
            headers=admin_headers,
            json={"agent_id": "default", "title": "租户A对话"},
        )
        conv_id_a = create_a.json()["data"]["conversation_id"]

        # 租户B不应看到租户A的对话
        list_b = test_client.get(
            "/api/agent/conversations",
            headers=demo_headers,
        )
        conv_ids_b = [c["conversation_id"] for c in list_b.json()["data"]]
        assert conv_id_a not in conv_ids_b

        # 租户B不能获取租户A的对话详情
        get_b = test_client.get(
            f"/api/agent/conversations/{conv_id_a}",
            headers=demo_headers,
        )
        assert get_b.json()["code"] == 4041

        # 租户B不能删除租户A的对话
        del_b = test_client.delete(
            f"/api/agent/conversations/{conv_id_a}",
            headers=demo_headers,
        )
        assert del_b.json()["code"] == 4041
