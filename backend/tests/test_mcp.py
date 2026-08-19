"""MCP API 测试。

测试 MCP Server 管理 API 层（不测试外部进程连接）。
"""

import pytest


class TestMCPServers:
    """MCP Server 管理测试套件。"""

    def test_mcp_servers_list(self, test_client, admin_headers):
        """测试已连接 Server 列表（至少有默认 weather server）。"""
        response = test_client.get("/api/mcp/servers", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert isinstance(data["data"], list)
        assert len(data["data"]) >= 1

        # 验证默认 weather server 存在
        server_names = [s["name"] for s in data["data"]]
        assert "weather" in server_names

    def test_mcp_servers_list_unauthorized(self, test_client):
        """测试未认证不能访问 Server 列表。"""
        response = test_client.get("/api/mcp/servers")
        assert response.status_code == 401

    def test_mcp_register_server(self, test_client, admin_headers):
        """测试注册新 MCP Server。"""
        response = test_client.post(
            "/api/mcp/servers",
            headers=admin_headers,
            json={
                "name": "test-server",
                "command": "python",
                "args": ["-m", "some.module"],
                "env": {},
                "description": "测试用 MCP Server",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["name"] == "test-server"
        assert data["data"]["command"] == "python"
        assert data["data"]["status"] == "registered"

        # 确认出现在列表中
        list_resp = test_client.get("/api/mcp/servers", headers=admin_headers)
        server_names = [s["name"] for s in list_resp.json()["data"]]
        assert "test-server" in server_names

    def test_mcp_unregister_server(self, test_client, admin_headers):
        """测试注销 MCP Server。"""
        # 先注册
        test_client.post(
            "/api/mcp/servers",
            headers=admin_headers,
            json={
                "name": "temp-server",
                "command": "echo",
                "args": [],
                "description": "临时服务器",
            },
        )

        # 注销
        response = test_client.delete(
            "/api/mcp/servers/temp-server",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["deleted"] is True

        # 确认已从列表移除
        list_resp = test_client.get("/api/mcp/servers", headers=admin_headers)
        server_names = [s["name"] for s in list_resp.json()["data"]]
        assert "temp-server" not in server_names

    def test_mcp_unregister_nonexistent(self, test_client, admin_headers):
        """测试注销不存在的 Server。"""
        response = test_client.delete(
            "/api/mcp/servers/nonexistent-server",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 4041


class TestMCPConnections:
    """MCP 连接管理测试套件。"""

    def test_mcp_connections_list(self, test_client, admin_headers):
        """测试列出所有 MCP 连接（初始为空列表）。"""
        response = test_client.get("/api/mcp/connections", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert isinstance(data["data"], list)

    def test_mcp_connections_unauthorized(self, test_client):
        """测试未认证不能访问连接列表。"""
        response = test_client.get("/api/mcp/connections")
        assert response.status_code == 401

    def test_mcp_connect_nonexistent_server(self, test_client, admin_headers):
        """测试连接不存在的 Server（应返回 4041）。"""
        response = test_client.post(
            "/api/mcp/connect",
            headers=admin_headers,
            json={"server_name": "nonexistent-server"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 4041

    def test_mcp_call_tool_not_connected(self, test_client, admin_headers):
        """测试调用未连接 Server 的工具（应返回失败）。"""
        response = test_client.post(
            "/api/mcp/call-tool",
            headers=admin_headers,
            json={
                "server_name": "nonexistent",
                "tool_name": "some_tool",
                "arguments": {},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["success"] is False
