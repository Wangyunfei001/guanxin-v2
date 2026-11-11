"""MCP Server 租户隔离测试。

注册表与连接缓存都按 (tenant_id, server_name) 分键，任意租户的管理员
只能注册、查看、注销自己租户的 Server。
"""

import uuid

import pytest


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


class TestMCPRegistryTenantIsolation:
    """注册表的租户隔离。"""

    def test_server_registered_by_one_tenant_is_invisible_to_another(
        self, test_client, admin_headers, demo_headers
    ):
        """其他租户注册的 Server 不出现在本租户的列表里。"""
        name = _unique("isolated")
        response = test_client.post(
            "/api/mcp/servers",
            headers=admin_headers,
            json={
                "name": name,
                "command": "python",
                "args": ["-m", "some.module"],
                "description": "租户 A 私有",
            },
        )
        assert response.status_code == 200

        tenant_a_names = [
            item["name"]
            for item in test_client.get(
                "/api/mcp/servers", headers=admin_headers
            ).json()["data"]
        ]
        tenant_b_names = [
            item["name"]
            for item in test_client.get(
                "/api/mcp/servers", headers=demo_headers
            ).json()["data"]
        ]

        assert name in tenant_a_names
        assert name not in tenant_b_names

    def test_tenant_cannot_delete_another_tenant_server(
        self, test_client, admin_headers, demo_headers
    ):
        """其他租户的管理员删不掉本租户的 Server。"""
        name = _unique("guarded")
        test_client.post(
            "/api/mcp/servers",
            headers=admin_headers,
            json={"name": name, "command": "python", "args": []},
        )

        # 租户 B 尝试删除租户 A 的 Server
        response = test_client.delete(
            f"/api/mcp/servers/{name}", headers=demo_headers
        )
        assert response.json()["code"] == 4041

        # 租户 A 的 Server 仍在
        names = [
            item["name"]
            for item in test_client.get(
                "/api/mcp/servers", headers=admin_headers
            ).json()["data"]
        ]
        assert name in names

    def test_same_name_in_two_tenants_keeps_separate_configs(
        self, test_client, admin_headers, demo_headers
    ):
        """两个租户可以注册同名 Server，配置互不覆盖。"""
        name = _unique("shared-name")
        test_client.post(
            "/api/mcp/servers",
            headers=admin_headers,
            json={"name": name, "command": "tenant-a-binary", "args": ["--a"]},
        )
        test_client.post(
            "/api/mcp/servers",
            headers=demo_headers,
            json={"name": name, "command": "tenant-b-binary", "args": ["--b"]},
        )

        tenant_a = next(
            item
            for item in test_client.get(
                "/api/mcp/servers", headers=admin_headers
            ).json()["data"]
            if item["name"] == name
        )
        tenant_b = next(
            item
            for item in test_client.get(
                "/api/mcp/servers", headers=demo_headers
            ).json()["data"]
            if item["name"] == name
        )

        assert tenant_a["command"] == "tenant-a-binary"
        assert tenant_b["command"] == "tenant-b-binary"

    def test_each_tenant_keeps_its_own_default_weather_server(
        self, test_client, admin_headers, demo_headers
    ):
        """两个预设租户各自拥有默认 weather Server。"""
        for headers in (admin_headers, demo_headers):
            names = [
                item["name"]
                for item in test_client.get(
                    "/api/mcp/servers", headers=headers
                ).json()["data"]
            ]
            assert "weather" in names

    def test_agent_config_cannot_enable_another_tenant_server(
        self, test_client, admin_headers, demo_headers
    ):
        """Agent 配置只能启用本租户注册过的 Server。"""
        name = _unique("other-tenant")
        test_client.post(
            "/api/mcp/servers",
            headers=admin_headers,
            json={"name": name, "command": "python", "args": []},
        )

        response = test_client.put(
            "/api/agent/config",
            headers=demo_headers,
            json={
                "model": "deepseek-v4-pro",
                "temperature": 0.7,
                "max_tokens": 4096,
                "system_prompt": "test",
                "enabled_tools": ["kb_retrieval"],
                "enabled_skills": ["text_summary"],
                "mcp_servers": [name],
            },
        )
        assert response.status_code == 422
        assert "未知 MCP Server" in response.json()["detail"]


class TestMCPClientTenantIsolation:
    """连接缓存的租户隔离。"""

    def test_tool_definitions_are_scoped_to_tenant(self):
        """工具定义只对所属租户可见。"""
        from app.mcp.client import MCPClient

        client = MCPClient()
        client._connections[("tenant-a", "weather")] = {
            "command": "python",
            "args": [],
            "env": {},
            "status": "connected",
            "tools": [
                {
                    "name": "get_weather",
                    "description": "",
                    "input_schema": {},
                    "output_schema": None,
                    "annotations": {},
                    "metadata": {},
                }
            ],
        }

        assert client.get_tool_definitions("tenant-a")
        assert client.get_tool_definitions("tenant-b") == []

    def test_connection_lookup_requires_matching_tenant(self):
        """连接信息不能跨租户读到。"""
        from app.mcp.client import MCPClient

        client = MCPClient()
        client._connections[("tenant-a", "weather")] = {
            "command": "python",
            "args": [],
            "env": {},
            "status": "connected",
            "tools": [],
        }

        assert client.get_connection("tenant-a", "weather") is not None
        assert client.get_connection("tenant-b", "weather") is None

    def test_disconnect_only_affects_own_tenant(self):
        """断开连接只影响本租户。"""
        from app.mcp.client import MCPClient

        client = MCPClient()
        for tenant_id in ("tenant-a", "tenant-b"):
            client._connections[(tenant_id, "weather")] = {
                "command": "python",
                "args": [],
                "env": {},
                "status": "connected",
                "tools": [],
            }

        assert client.disconnect("tenant-b", "weather") is True
        assert client.get_connection("tenant-a", "weather") is not None
        assert client.get_connection("tenant-b", "weather") is None


class TestMCPServerDisclosure:
    """MCP Server 描述不泄露密钥与命令行。"""

    def test_env_values_never_appear_in_response(
        self, test_client, admin_headers
    ):
        """env 的值不会出现在任何角色的响应里。"""
        secret = "sk-super-secret-value"
        name = _unique("with-env")
        test_client.post(
            "/api/mcp/servers",
            headers=admin_headers,
            json={
                "name": name,
                "command": "python",
                "args": ["-m", "some.module"],
                "env": {"OPENAI_API_KEY": secret},
            },
        )

        for headers in (admin_headers,):
            body = test_client.get(
                "/api/mcp/servers", headers=headers
            ).text
            assert secret not in body

    def test_admin_sees_env_keys_but_not_values(self, test_client, admin_headers):
        """管理员能看到环境变量名，看不到值。"""
        secret = "sk-another-secret"
        name = _unique("admin-env")
        test_client.post(
            "/api/mcp/servers",
            headers=admin_headers,
            json={
                "name": name,
                "command": "python",
                "args": [],
                "env": {"OPENAI_API_KEY": secret},
            },
        )

        server = next(
            item
            for item in test_client.get(
                "/api/mcp/servers", headers=admin_headers
            ).json()["data"]
            if item["name"] == name
        )
        assert server["env_keys"] == ["OPENAI_API_KEY"]
        assert "env" not in server

    def test_non_admin_sees_no_command_line_or_env(
        self, test_client, admin_headers, user_headers
    ):
        """普通用户看不到命令行与环境变量信息。"""
        secret = "sk-user-visible-secret"
        name = _unique("user-env")
        test_client.post(
            "/api/mcp/servers",
            headers=admin_headers,
            json={
                "name": name,
                "command": "/opt/venv/bin/python",
                "args": ["-m", "some.module"],
                "env": {"OPENAI_API_KEY": secret},
            },
        )

        response = test_client.get("/api/mcp/servers", headers=user_headers)
        assert response.status_code == 200
        body = response.text
        assert secret not in body
        assert "/opt/venv/bin/python" not in body

        server = next(
            item
            for item in response.json()["data"]
            if item["name"] == name
        )
        assert "command" not in server
        assert "args" not in server
        assert "env" not in server
        assert "env_keys" not in server
        # 非管理员仍然看得到基本信息
        assert server["description"] is not None
