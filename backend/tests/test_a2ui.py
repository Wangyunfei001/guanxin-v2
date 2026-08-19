"""A2UI API 测试。

测试组件目录、模板列表、渲染和 Schema 校验。
"""

import pytest


class TestA2UICatalog:
    """A2UI 组件目录测试套件。"""

    def test_a2ui_catalog(self, test_client, admin_headers):
        """测试返回 5 类组件。"""
        response = test_client.get("/api/a2ui/catalog", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert isinstance(data["data"], list)
        assert len(data["data"]) == 5

        component_types = [c["component_type"] for c in data["data"]]
        assert "form_card" in component_types
        assert "info_card" in component_types
        assert "list_card" in component_types
        assert "confirm_card" in component_types
        assert "chart_card" in component_types

    def test_a2ui_catalog_unauthorized(self, test_client):
        """测试未认证不能访问目录。"""
        response = test_client.get("/api/a2ui/catalog")
        assert response.status_code == 401

    def test_a2ui_component_spec(self, test_client, admin_headers):
        """测试获取指定组件类型的 Schema 规范。"""
        response = test_client.get(
            "/api/a2ui/catalog/form_card",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["component_type"] == "form_card"
        assert "props_schema" in data["data"]

    def test_a2ui_component_spec_not_found(self, test_client, admin_headers):
        """测试获取不存在的组件类型。"""
        response = test_client.get(
            "/api/a2ui/catalog/nonexistent_card",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 4041


class TestA2UITemplates:
    """A2UI 模板测试套件。"""

    def test_a2ui_templates(self, test_client, admin_headers):
        """测试返回预定义模板列表。"""
        response = test_client.get("/api/a2ui/templates", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert isinstance(data["data"], list)
        assert len(data["data"]) >= 5

        template_names = [t["name"] for t in data["data"]]
        assert "kb_result" in template_names
        assert "skill_result" in template_names
        assert "confirm_action" in template_names
        assert "data_analysis" in template_names
        assert "error" in template_names

    def test_a2ui_templates_have_description(self, test_client, admin_headers):
        """测试模板列表包含描述。"""
        response = test_client.get("/api/a2ui/templates", headers=admin_headers)
        data = response.json()
        for template in data["data"]:
            assert "name" in template
            assert "description" in template


class TestA2UIRender:
    """A2UI 渲染测试套件。"""

    def test_a2ui_render_kb_result(self, test_client, admin_headers):
        """测试渲染知识库检索结果模板。"""
        response = test_client.post(
            "/api/a2ui/render",
            headers=admin_headers,
            json={
                "template_name": "kb_result",
                "data": [
                    {
                        "content": "这是检索到的内容片段",
                        "filename": "test.txt",
                        "score": 0.95,
                    }
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["component_type"] == "list_card"
        assert "columns" in data["data"]["props"]
        assert "rows" in data["data"]["props"]

    def test_a2ui_render_confirm_action(self, test_client, admin_headers):
        """测试渲染确认操作模板。"""
        response = test_client.post(
            "/api/a2ui/render",
            headers=admin_headers,
            json={
                "template_name": "confirm_action",
                "data": {
                    "title": "确认删除",
                    "message": "确定要删除这个文档吗？",
                    "danger": True,
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["component_type"] == "confirm_card"
        assert data["data"]["props"]["title"] == "确认删除"
        assert data["data"]["props"]["danger"] is True

    def test_a2ui_render_data_analysis(self, test_client, admin_headers):
        """测试渲染数据分析模板。"""
        response = test_client.post(
            "/api/a2ui/render",
            headers=admin_headers,
            json={
                "template_name": "data_analysis",
                "data": {
                    "title": "销售数据分析",
                    "stats": {"mean": 100.5, "max": 200, "min": 50},
                    "chart_data": {
                        "type": "bar",
                        "labels": ["Q1", "Q2", "Q3"],
                        "values": [100, 150, 200],
                    },
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["component_type"] == "info_card"
        assert len(data["data"].get("children", [])) > 0

    def test_a2ui_render_unknown_template(self, test_client, admin_headers):
        """测试渲染不存在的模板。"""
        response = test_client.post(
            "/api/a2ui/render",
            headers=admin_headers,
            json={
                "template_name": "nonexistent_template",
                "data": {},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 4041

    def test_a2ui_render_dynamic(self, test_client, admin_headers):
        """测试动态构建 A2UI Schema。"""
        response = test_client.post(
            "/api/a2ui/render-dynamic",
            headers=admin_headers,
            json={
                "component_type": "info_card",
                "title": "动态卡片",
                "props": {"content": "动态内容"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["component_type"] == "info_card"
        assert data["data"]["props"]["title"] == "动态卡片"
        assert data["data"]["props"]["content"] == "动态内容"

    def test_a2ui_render_dynamic_with_children(self, test_client, admin_headers):
        """测试动态构建带子组件的 Schema。"""
        response = test_client.post(
            "/api/a2ui/render-dynamic",
            headers=admin_headers,
            json={
                "component_type": "info_card",
                "title": "父卡片",
                "props": {},
                "children": [
                    {
                        "component_type": "chart_card",
                        "props": {"title": "子图表"},
                    }
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert len(data["data"]["children"]) == 1


class TestA2UIValidate:
    """A2UI Schema 校验测试套件。"""

    def test_a2ui_preview_valid_schema(self, test_client, admin_headers):
        """测试校验合法 Schema。"""
        response = test_client.post(
            "/api/a2ui/preview",
            headers=admin_headers,
            json={
                "schema": {
                    "component_type": "info_card",
                    "props": {
                        "title": "测试卡片",
                        "content": "内容",
                    },
                }
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["valid"] is True

    def test_a2ui_preview_invalid_component_type(self, test_client, admin_headers):
        """测试校验未知组件类型。"""
        response = test_client.post(
            "/api/a2ui/preview",
            headers=admin_headers,
            json={
                "schema": {
                    "component_type": "nonexistent_card",
                    "props": {},
                }
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 4221
        assert data["data"]["valid"] is False

    def test_a2ui_preview_missing_component_type(self, test_client, admin_headers):
        """测试校验缺少 component_type。"""
        response = test_client.post(
            "/api/a2ui/preview",
            headers=admin_headers,
            json={
                "schema": {
                    "props": {},
                }
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 4221
        assert data["data"]["valid"] is False

    def test_a2ui_preview_valid_with_children(self, test_client, admin_headers):
        """测试校验带合法子组件的 Schema。"""
        response = test_client.post(
            "/api/a2ui/preview",
            headers=admin_headers,
            json={
                "schema": {
                    "component_type": "info_card",
                    "props": {"title": "父"},
                    "children": [
                        {
                            "component_type": "chart_card",
                            "props": {"title": "子"},
                        }
                    ],
                }
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["valid"] is True
