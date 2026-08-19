"""Skill API 测试。

测试技能列表、详情、执行和 DAG 编排。
"""

import pytest

from app.models.skill_context import SkillContext
from app.skills.executor import SkillExecutor
from app.skills.registry import get_skill_registry


class TestSkillAPI:
    """Skill API 测试套件。"""

    def test_skill_list(self, test_client, admin_headers):
        """测试 Skill 列表返回 data_analysis + text_summary。"""
        response = test_client.get("/api/skills", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert isinstance(data["data"], list)
        assert len(data["data"]) >= 2

        skill_names = [s["name"] for s in data["data"]]
        assert "data_analysis" in skill_names
        assert "text_summary" in skill_names

    def test_skill_list_unauthorized(self, test_client):
        """测试未认证不能访问 Skill 列表。"""
        response = test_client.get("/api/skills")
        assert response.status_code == 401

    def test_skill_detail_text_summary(self, test_client, admin_headers):
        """测试获取 text_summary 技能详情。"""
        response = test_client.get(
            "/api/skills/text_summary",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["name"] == "text_summary"
        assert data["data"]["display_name"] == "文本摘要"
        assert len(data["data"]["params"]) >= 1

        # 验证参数 schema
        param_names = [p["name"] for p in data["data"]["params"]]
        assert "text" in param_names

    def test_skill_detail_data_analysis(self, test_client, admin_headers):
        """测试获取 data_analysis 技能详情。"""
        response = test_client.get(
            "/api/skills/data_analysis",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["name"] == "data_analysis"
        assert data["data"]["display_name"] == "数据分析"

        param_names = [p["name"] for p in data["data"]["params"]]
        assert "data" in param_names
        assert "analysis_type" in param_names

    def test_skill_detail_not_found(self, test_client, admin_headers):
        """测试获取不存在的技能详情。"""
        response = test_client.get(
            "/api/skills/nonexistent_skill",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 4041
        assert "未找到" in data["message"]

    def test_skill_execute_text_summary(self, test_client, admin_headers):
        """测试执行 text_summary 技能。"""
        text = (
            "人工智能是计算机科学的一个分支。"
            "它致力于研究、开发用于模拟人类智能的理论和方法。"
            "机器学习是人工智能的核心技术之一。"
            "深度学习是机器学习的一个子领域。"
            "自然语言处理是人工智能的重要应用方向。"
        )
        response = test_client.post(
            "/api/skills/execute",
            headers=admin_headers,
            json={
                "skill_name": "text_summary",
                "params": {"text": text, "max_sentences": 2},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["success"] is True
        assert "summary" in data["data"]["output"]
        assert "keywords" in data["data"]["output"]
        assert data["data"]["output"]["original_length"] == len(text)

    def test_skill_execute_data_analysis(self, test_client, admin_headers):
        """测试执行 data_analysis 技能。"""
        response = test_client.post(
            "/api/skills/execute",
            headers=admin_headers,
            json={
                "skill_name": "data_analysis",
                "params": {"data": [1, 2, 3, 4, 5], "analysis_type": "basic"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["success"] is True
        output = data["data"]["output"]
        assert output["count"] == 5
        assert output["mean"] == 3.0
        assert output["median"] == 3.0
        assert output["max"] == 5
        assert output["min"] == 1

    def test_skill_execute_data_analysis_full(self, test_client, admin_headers):
        """测试执行 data_analysis 技能（full 模式含图表数据）。"""
        response = test_client.post(
            "/api/skills/execute",
            headers=admin_headers,
            json={
                "skill_name": "data_analysis",
                "params": {"data": [10, 20, 30], "analysis_type": "full"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["success"] is True
        output = data["data"]["output"]
        assert "chart_data" in output
        assert output["chart_data"]["type"] == "bar"
        assert len(output["chart_data"]["values"]) == 3

    def test_skill_execute_missing_param(self, test_client, admin_headers):
        """测试执行技能时缺少必填参数。"""
        response = test_client.post(
            "/api/skills/execute",
            headers=admin_headers,
            json={
                "skill_name": "text_summary",
                "params": {},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["success"] is False
        assert "缺少必填参数" in data["data"]["error"]

    def test_skill_execute_unknown_skill(self, test_client, admin_headers):
        """测试执行不存在的技能。"""
        response = test_client.post(
            "/api/skills/execute",
            headers=admin_headers,
            json={
                "skill_name": "nonexistent",
                "params": {},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["success"] is False
        assert "未注册" in data["data"]["error"]

    def test_skill_execute_empty_text(self, test_client, admin_headers):
        """测试文本摘要传入空文本。"""
        response = test_client.post(
            "/api/skills/execute",
            headers=admin_headers,
            json={
                "skill_name": "text_summary",
                "params": {"text": ""},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["success"] is False
        assert "空" in data["data"]["error"]


class TestSkillOrchestration:
    """Skill DAG 编排测试套件（直接测试 SkillExecutor）。"""

    def test_execute_chain_success(self):
        """测试线性 DAG 编排成功执行。"""
        executor = SkillExecutor()
        context = SkillContext(tenant_id="tenant-a", user_id="admin-001")

        results = executor.execute_chain(
            steps=[
                {
                    "name": "data_analysis",
                    "params": {"data": [1, 2, 3, 4, 5]},
                },
                {
                    "name": "text_summary",
                    "params": {
                        "text": "这是第一句话。这是第二句话。这是第三句话。"
                    },
                },
            ],
            context=context,
        )

        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is True

    def test_execute_chain_stops_on_failure(self):
        """测试 DAG 编排在某步失败时停止。"""
        executor = SkillExecutor()
        context = SkillContext(tenant_id="tenant-a", user_id="admin-001")

        results = executor.execute_chain(
            steps=[
                {
                    "name": "text_summary",
                    "params": {},  # 缺少必填参数，会失败
                },
                {
                    "name": "data_analysis",
                    "params": {"data": [1, 2, 3]},
                },
            ],
            context=context,
        )

        # 第一步失败，第二步不应执行
        assert len(results) == 1
        assert results[0].success is False

    def test_skill_registry_initialized(self):
        """测试技能注册表已正确初始化。"""
        registry = get_skill_registry()
        skills = registry.list_skills()
        skill_names = [s.name for s in skills]
        assert "data_analysis" in skill_names
        assert "text_summary" in skill_names
