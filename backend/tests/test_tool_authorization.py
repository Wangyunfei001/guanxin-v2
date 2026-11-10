"""工具授权一致性测试。

Agent 目录与工作流目录共用同一份可见性与风险判定：
- 管理员禁用 MCP 工具后，两条路径都看不到它；
- Skill 必须显式声明 effect，风险判定 fail-closed。
"""

import pytest

from app.agent.tool_catalog import build_tool_catalog, runtime_tools
from app.models.agent import AgentConfig, get_agent_config_store
from app.models.skill import VALID_SKILL_EFFECTS
from app.skills.registry import get_skill_registry
from app.workflows.catalog import build_tool_catalog as build_workflow_catalog

WEATHER_TOOL = "mcp__weather__get_weather"


def _agent_config() -> AgentConfig:
    return get_agent_config_store().get_or_create_default("tenant-a")


class TestSharedCatalog:
    """两条路径共用一份判定。"""

    @pytest.mark.asyncio
    async def test_disabled_mcp_tool_is_hidden_from_both_catalogs(
        self, test_client, admin_headers
    ):
        """禁用开关在 Agent 与工作流两条路径上都生效。"""
        connect = test_client.post(
            "/api/mcp/connect", headers=admin_headers, json={"server_name": "weather"}
        )
        assert connect.status_code == 200

        config = _agent_config()
        assert "weather" in config.mcp_servers

        entries = await build_tool_catalog(
            config, tenant_id="tenant-a", user_id="admin-001", user_role="admin"
        )
        assert WEATHER_TOOL in {entry.spec.name for entry in entries}
        workflow_tools = build_workflow_catalog(config, "admin")
        assert WEATHER_TOOL in {tool.name for tool in workflow_tools}

        # 管理员禁用该工具
        disable = test_client.put(
            "/api/mcp/servers/weather/tools/get_weather/policy",
            headers=admin_headers,
            json={"enabled": False, "effect": "read", "approval_required": False},
        )
        assert disable.status_code == 200

        try:
            after = await build_tool_catalog(
                config,
                tenant_id="tenant-a",
                user_id="admin-001",
                user_role="admin",
                ensure_mcp=False,
            )
            assert WEATHER_TOOL not in {entry.spec.name for entry in after}

            workflow_after = build_workflow_catalog(config, "admin")
            assert WEATHER_TOOL not in {tool.name for tool in workflow_after}
        finally:
            restore = test_client.put(
                "/api/mcp/servers/weather/tools/get_weather/policy",
                headers=admin_headers,
                json={"enabled": True, "effect": "read", "approval_required": False},
            )
            assert restore.status_code == 200

    def test_risk_classification_is_identical_on_both_paths(self):
        """同一工具在两条路径上的风险等级一致。"""
        config = AgentConfig(
            agent_id="default",
            tenant_id="tenant-risk",
            name="risk",
            enabled_tools=["kb_retrieval"],
            enabled_skills=["create_user", "query_users", "text_summary"],
        )

        from app.agent.tool_catalog import discover_tool_specs

        specs = {
            spec.name: spec.effect
            for spec in discover_tool_specs(
                config, tenant_id="tenant-risk", user_role="admin"
            )
        }
        tools = {
            tool.name: tool.risk
            for tool in build_workflow_catalog(config, "admin")
            if tool.name != "kb_retrieval"
        }

        assert specs, "目录不应为空"
        assert specs == tools


class TestSkillEffectIsDeclared:
    """Skill 的 effect 必须显式声明且合法。"""

    def test_every_registered_skill_declares_a_valid_effect(self):
        """所有已注册 Skill 都声明了合法 effect。"""
        registry = get_skill_registry()
        registry.register_all()
        skills = registry.list_skills()
        assert skills
        for skill in skills:
            assert skill.metadata.effect in VALID_SKILL_EFFECTS, (
                f"Skill {skill.name} 的 effect 非法: {skill.metadata.effect!r}"
            )

    def test_write_skills_are_never_runtime_tools(self):
        """写 Skill 不进入免审批的 runtime 工具集合。"""
        registry = get_skill_registry()
        registry.register_all()
        config = AgentConfig(
            agent_id="default",
            tenant_id="tenant-effect",
            name="effect",
            enabled_tools=["kb_retrieval"],
            enabled_skills=["create_user", "update_user", "delete_user", "text_summary"],
        )

        from app.agent.tool_catalog import discover_tool_specs

        specs = discover_tool_specs(
            config, tenant_id="tenant-effect", user_role="admin"
        )
        for spec in specs:
            if spec.source_name in {"create_user", "update_user", "delete_user"}:
                assert spec.effect == "write"
                assert spec.approval_required is True
            if spec.source_name == "text_summary":
                assert spec.effect == "read"
                assert spec.approval_required is False

    def test_unknown_effect_is_never_auto_executed(self):
        """effect 为 unknown 的工具不会被免审批执行。"""
        from app.agent.tool_catalog import ToolSpec, CatalogEntry

        entries = [
            CatalogEntry(
                spec=ToolSpec(
                    name="skill__mystery",
                    display_name="未知副作用",
                    description="",
                    source_type="skill",
                    source_name="mystery",
                    effect="unknown",
                    approval_required=True,
                )
            )
        ]
        assert runtime_tools(entries) == []

    def test_skill_with_invalid_effect_is_not_registered(self):
        """effect 非法的 Skill 不会被注册进目录。"""
        from app.skills.base import BaseSkill
        from app.models.skill import SkillMetadata

        class BadEffectSkill(BaseSkill):
            def _define_metadata(self) -> SkillMetadata:
                metadata = SkillMetadata(
                    name="bad_effect",
                    display_name="非法副作用",
                    description="测试用",
                    effect="read",
                )
                metadata.effect = "delete-everything"  # 绕过类型标注
                return metadata

            async def execute(self, params, context):
                raise NotImplementedError

        registry = get_skill_registry()
        registry.unregister("bad_effect")
        registry.register(BadEffectSkill())
        assert registry.get_skill("bad_effect") is None
