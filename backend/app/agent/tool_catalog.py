"""Unified, RBAC-filtered tool catalog for Agent, Research and Workflow execution.

工具的**可见性与风险等级只有一份判定**：:func:`discover_tool_specs`。
Agent 目录与工作流目录都从它派生，因此 MCP 禁用开关与风险分级不可能在
两条路径上漂移——这正是之前「禁用开关在工作流侧失效」「工作流风险分类
fail-open」两个缺陷的根因。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field, create_model

from app.agent.tools import kb_retrieval_tool_factory
from app.mcp.client import get_mcp_client
from app.models.agent import AgentConfig
from app.models.skill_context import SkillContext
from app.services.mcp_policy_store import get_mcp_tool_policy_store
from app.skills.executor import ADMIN_ONLY_SKILLS
from app.skills.registry import get_skill_registry


class ToolSpec(BaseModel):
    name: str
    display_name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    source_type: Literal["builtin", "skill", "mcp", "provider"]
    source_name: str
    effect: Literal["read", "write", "unknown"] = "unknown"
    approval_required: bool = True
    enabled: bool = True


@dataclass
class CatalogEntry:
    spec: ToolSpec
    tool: BaseTool | None = None


def _python_type(kind: str) -> Any:
    return {
        "string": str,
        "number": float,
        "integer": int,
        "boolean": bool,
        "array": list[Any],
        "object": dict[str, Any],
    }.get(kind, Any)


def _model_from_properties(name: str, properties: dict[str, Any], required: set[str]) -> type[BaseModel]:
    fields: dict[str, tuple[Any, Any]] = {}
    for field_name, raw in properties.items():
        spec = raw if isinstance(raw, dict) else {}
        annotation = _python_type(str(spec.get("type", "string")))
        default = ... if field_name in required else spec.get("default", None)
        fields[field_name] = (
            annotation,
            Field(default=default, description=str(spec.get("description", ""))),
        )
    return create_model(name, **fields)


def _skill_schema(skill: Any) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []
    for param in skill.metadata.params:
        item: dict[str, Any] = {
            "type": "integer" if param.type == "number" and isinstance(param.default, int) else param.type,
            "description": param.description,
        }
        if param.default is not None:
            item["default"] = param.default
        if param.options:
            item["enum"] = param.options
        properties[param.name] = item
        if param.required:
            required.append(param.name)
    return {"type": "object", "properties": properties, "required": required}


def _skill_tool(skill: Any, context: SkillContext) -> BaseTool:
    schema = _skill_schema(skill)
    args_model = _model_from_properties(
        f"Skill{skill.name.title().replace('_', '')}Args",
        schema["properties"],
        set(schema["required"]),
    )

    async def run_skill(**kwargs: Any) -> dict[str, Any]:
        validation_error = skill.validate_params(kwargs)
        if validation_error:
            return {"success": False, "error": validation_error}
        result = await skill.execute(kwargs, context)
        return result.to_dict()

    return StructuredTool.from_function(
        coroutine=run_skill,
        name=f"skill__{skill.name}",
        description=skill.metadata.description,
        args_schema=args_model,
    )


def _mcp_tool(tenant_id: str, server_name: str, definition: dict[str, Any]) -> BaseTool:
    schema = definition.get("input_schema") or {"type": "object", "properties": {}}
    args_model = _model_from_properties(
        f"MCP{server_name.title()}{definition['tool_name'].title().replace('_', '')}Args",
        schema.get("properties", {}),
        set(schema.get("required", [])),
    )

    async def call_mcp(**kwargs: Any) -> dict[str, Any]:
        from app.mcp.client import get_mcp_client

        return await get_mcp_client().call_tool(
            tenant_id,
            server_name,
            definition["tool_name"],
            kwargs,
        )

    return StructuredTool.from_function(
        coroutine=call_mcp,
        name=definition["full_name"],
        description=definition.get("description") or definition["full_name"],
        args_schema=args_model,
    )


def _skill_spec(skill: Any) -> ToolSpec:
    """Skill 的工具描述。风险判定 fail-closed：非 read/write 一律 unknown。"""
    effect = skill.metadata.effect
    if effect not in {"read", "write"}:
        effect = "unknown"
    return ToolSpec(
        name=f"skill__{skill.name}",
        display_name=skill.metadata.display_name,
        description=skill.metadata.description,
        input_schema=_skill_schema(skill),
        source_type="skill",
        source_name=skill.name,
        effect=effect,
        approval_required=bool(skill.metadata.approval_required or effect != "read"),
    )


def _mcp_spec(definition: dict[str, Any], policy: dict[str, Any]) -> ToolSpec:
    """MCP 工具的工具描述。风险取自租户策略。"""
    effect = policy.get("effect", "unknown")
    return ToolSpec(
        name=definition["full_name"],
        display_name=(
            definition.get("annotations", {}).get("title") or definition["tool_name"]
        ),
        description=definition.get("description", ""),
        input_schema=definition.get("input_schema", {}),
        source_type="mcp",
        source_name=definition["server_name"],
        effect=effect if effect in {"read", "write", "unknown"} else "unknown",
        approval_required=bool(policy.get("approval_required", True)),
    )


def _collect_shared(
    config: AgentConfig,
    *,
    tenant_id: str,
    user_role: str,
) -> list[tuple[ToolSpec, Any]]:
    """Skill 与 MCP 工具的可见性、风险等级，以及构造工具所需的对象。

    第二项是构造 LangChain 工具所需的原始对象（Skill 实例或 MCP 工具
    定义），工作流侧不需要它，只取描述。
    """
    collected: list[tuple[ToolSpec, Any]] = []

    registry = get_skill_registry()
    registry.register_all()
    for skill_name in config.enabled_skills:
        skill = registry.get_skill(skill_name)
        if skill is None:
            continue
        if user_role != "admin" and skill_name in ADMIN_ONLY_SKILLS:
            continue
        collected.append((_skill_spec(skill), skill))

    policy_store = get_mcp_tool_policy_store()
    for definition in get_mcp_client().get_tool_definitions(tenant_id):
        server_name = definition["server_name"]
        if server_name not in config.mcp_servers:
            continue
        policy = policy_store.get(tenant_id, server_name, definition["tool_name"])
        if policy is None:
            is_seed_weather = server_name == "weather" and definition["tool_name"] == "get_weather"
            policy = policy_store.ensure(
                tenant_id,
                server_name,
                definition["tool_name"],
                effect="read" if is_seed_weather else "unknown",
                approval_required=not is_seed_weather,
                metadata={"annotations": definition.get("annotations", {})},
            )
        if not policy.get("enabled", True):
            continue
        collected.append((_mcp_spec(definition, policy), definition))

    return collected


def discover_tool_specs(
    config: AgentConfig,
    *,
    tenant_id: str,
    user_role: str,
) -> list[ToolSpec]:
    """可见工具与风险等级的**唯一判定**——Agent 与工作流共用。

    不包含 kb_retrieval：两端的参数契约本就不同（Agent 用工具签名，
    工作流额外暴露 top_k），各自构造。
    """
    return [
        spec
        for spec, _payload in _collect_shared(
            config, tenant_id=tenant_id, user_role=user_role
        )
    ]


def _build_tool(
    spec: ToolSpec,
    payload: Any,
    *,
    tenant_id: str,
    context: SkillContext,
) -> BaseTool | None:
    """把共享描述还原成可执行的 LangChain 工具。"""
    if spec.source_type == "skill":
        return _skill_tool(payload, context)
    if spec.source_type == "mcp":
        return _mcp_tool(tenant_id, payload["server_name"], payload)
    return None


async def build_tool_catalog(
    config: AgentConfig,
    *,
    tenant_id: str,
    user_id: str,
    user_role: str,
    conversation_id: str = "",
    ensure_mcp: bool = True,
) -> list[CatalogEntry]:
    """Build the single source of truth for visible Agent capabilities."""
    entries: list[CatalogEntry] = []
    context = SkillContext(
        tenant_id=tenant_id,
        user_id=user_id,
        user_role=user_role,
        conversation_id=conversation_id,
    )

    if "kb_retrieval" in config.enabled_tools:
        tool = kb_retrieval_tool_factory()
        entries.append(
            CatalogEntry(
                spec=ToolSpec(
                    name="kb_retrieval",
                    display_name="知识库检索",
                    description="检索当前租户知识库中与问题相关的文档片段。",
                    input_schema=tool.args_schema.model_json_schema() if tool.args_schema else {},
                    source_type="builtin",
                    source_name="knowledge",
                    effect="read",
                    approval_required=False,
                ),
                tool=tool,
            )
        )

    if ensure_mcp:
        for server_name in config.mcp_servers:
            await get_mcp_client().ensure_available(tenant_id, server_name)

    for spec, payload in _collect_shared(
        config, tenant_id=tenant_id, user_role=user_role
    ):
        entries.append(
            CatalogEntry(
                spec=spec,
                tool=_build_tool(spec, payload, tenant_id=tenant_id, context=context),
            )
        )

    if "web_search" in config.enabled_tools:
        entries.append(
            CatalogEntry(
                spec=ToolSpec(
                    name="web_search",
                    display_name="Web Search",
                    description="搜索公开互联网中的新鲜信息并返回可验证来源。",
                    input_schema={
                        "type": "object",
                        "properties": {"query": {"type": "string", "description": "搜索问题"}},
                        "required": ["query"],
                    },
                    source_type="provider",
                    source_name="deepseek",
                    effect="read",
                    approval_required=False,
                )
            )
        )

    return entries


def serialize_tool_specs(entries: list[CatalogEntry]) -> list[dict[str, Any]]:
    return [entry.spec.model_dump() for entry in entries]


def runtime_tools(entries: list[CatalogEntry], names: list[str] | None = None) -> list[BaseTool]:
    allowed = set(names or [])
    return [
        entry.tool
        for entry in entries
        if entry.tool is not None
        and entry.spec.effect == "read"
        and not entry.spec.approval_required
        and (not allowed or entry.spec.name in allowed)
    ]


def catalog_prompt(entries: list[CatalogEntry]) -> str:
    return json.dumps(serialize_tool_specs(entries), ensure_ascii=False, indent=2)
