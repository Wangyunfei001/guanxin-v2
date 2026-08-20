"""RBAC-filtered workflow tool catalog and execution adapter."""

from __future__ import annotations

import asyncio
from typing import Any

from app.models.agent import AgentConfig
from app.models.skill_context import SkillContext
from app.services.retrieval_service import get_retrieval_service
from app.skills.executor import ADMIN_ONLY_SKILLS
from app.skills.registry import get_skill_registry
from app.workflows.models import ToolParameter, WorkflowTool


class WorkflowToolError(RuntimeError):
    pass


def _json_schema_parameters(schema: dict[str, Any]) -> list[ToolParameter]:
    properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
    required = set(schema.get("required", [])) if isinstance(schema, dict) else set()
    params: list[ToolParameter] = []
    for name, spec in properties.items():
        spec = spec if isinstance(spec, dict) else {}
        params.append(
            ToolParameter(
                name=name,
                type=spec.get("type", "string"),
                description=spec.get("description", ""),
                required=name in required,
                default=spec.get("default"),
                options=spec.get("enum", []),
            )
        )
    return params


def build_tool_catalog(config: AgentConfig, user_role: str) -> list[WorkflowTool]:
    tools: list[WorkflowTool] = []
    if "kb_retrieval" in config.enabled_tools:
        tools.append(
            WorkflowTool(
                name="kb_retrieval",
                display_name="知识库检索",
                description="检索当前租户知识库中与问题相关的文档片段。",
                category="knowledge",
                risk="read",
                parameters=[
                    ToolParameter(
                        name="query",
                        type="string",
                        description="检索问题",
                        required=True,
                    ),
                    ToolParameter(
                        name="top_k",
                        type="integer",
                        description="返回片段数",
                        required=False,
                        default=5,
                    ),
                ],
            )
        )

    registry = get_skill_registry()
    registry.register_all()
    for skill_name in config.enabled_skills:
        skill = registry.get_skill(skill_name)
        if skill is None:
            continue
        if user_role != "admin" and skill_name in ADMIN_ONLY_SKILLS:
            continue
        metadata = skill.metadata
        tools.append(
            WorkflowTool(
                name=f"skill__{skill_name}",
                display_name=metadata.display_name,
                description=metadata.description,
                category="skill",
                risk="write" if metadata.effect == "write" else "read",
                parameters=[ToolParameter.model_validate(item.to_dict()) for item in metadata.params],
            )
        )

    from app.mcp.client import get_mcp_client

    for definition in get_mcp_client().get_tool_definitions():
        if definition["server_name"] not in config.mcp_servers:
            continue
        tools.append(
            WorkflowTool(
                name=definition["full_name"],
                display_name=definition["tool_name"],
                description=definition.get("description", ""),
                category="mcp",
                risk="unknown",
                parameters=_json_schema_parameters(definition.get("input_schema", {})),
            )
        )
    return tools


def catalog_by_name(config: AgentConfig, user_role: str) -> dict[str, WorkflowTool]:
    return {tool.name: tool for tool in build_tool_catalog(config, user_role)}


def normalize_arguments(
    tool: WorkflowTool, arguments: dict[str, Any]
) -> dict[str, Any]:
    known = {param.name for param in tool.parameters}
    unknown = set(arguments) - known
    if unknown and tool.category != "mcp":
        raise WorkflowToolError(f"工具 {tool.name} 包含未知参数: {', '.join(sorted(unknown))}")
    normalized = dict(arguments)
    for param in tool.parameters:
        if param.name not in normalized:
            if param.required:
                normalized[param.name] = f"$inputs.{param.name}"
            elif param.default is not None:
                normalized[param.name] = param.default
    return normalized


def _lookup_path(value: Any, path: list[str]) -> Any:
    current = value
    for item in path:
        if isinstance(current, dict) and item in current:
            current = current[item]
        elif isinstance(current, list) and item.isdigit() and int(item) < len(current):
            current = current[int(item)]
        else:
            raise WorkflowToolError(f"无法解析步骤结果路径: {'.'.join(path)}")
    return current


def resolve_arguments(
    value: Any,
    *,
    inputs: dict[str, Any],
    outputs: dict[str, Any],
) -> tuple[Any, set[str]]:
    missing: set[str] = set()
    if isinstance(value, str) and value.startswith("$inputs."):
        name = value.removeprefix("$inputs.")
        if name not in inputs or inputs[name] in (None, ""):
            missing.add(name)
            return value, missing
        return inputs[name], missing
    if isinstance(value, str) and value.startswith("$steps."):
        pieces = value.split(".")
        if len(pieces) < 3:
            raise WorkflowToolError(f"非法步骤引用: {value}")
        step_id = pieces[1]
        if step_id not in outputs:
            raise WorkflowToolError(f"前序步骤尚无结果: {step_id}")
        return _lookup_path(outputs[step_id], pieces[2:]), missing
    if isinstance(value, dict):
        resolved: dict[str, Any] = {}
        for key, item in value.items():
            resolved_item, child_missing = resolve_arguments(
                item, inputs=inputs, outputs=outputs
            )
            resolved[key] = resolved_item
            missing.update(child_missing)
        return resolved, missing
    if isinstance(value, list):
        resolved_list = []
        for item in value:
            resolved_item, child_missing = resolve_arguments(
                item, inputs=inputs, outputs=outputs
            )
            resolved_list.append(resolved_item)
            missing.update(child_missing)
        return resolved_list, missing
    return value, missing


def input_fields(tool: WorkflowTool, names: set[str]) -> list[dict[str, Any]]:
    by_name = {param.name: param for param in tool.parameters}
    fields = []
    for name in sorted(names):
        param = by_name.get(name, ToolParameter(name=name, required=True))
        field_type = "select" if param.options else param.type
        if name.lower() == "email":
            field_type = "email"
        if field_type not in {"string", "email", "number", "integer", "boolean", "array", "select"}:
            field_type = "string"
        fields.append(
            {
                "name": name,
                "label": param.description or name,
                "type": field_type,
                "required": True,
                "default": param.default,
                "options": param.options,
            }
        )
    return fields


async def execute_tool(
    tool: WorkflowTool,
    arguments: dict[str, Any],
    context: SkillContext,
) -> dict[str, Any]:
    if tool.name == "kb_retrieval":
        results = await asyncio.to_thread(
            get_retrieval_service().retrieve,
            str(arguments.get("query", "")),
            context.tenant_id,
            int(arguments.get("top_k", 5)),
        )
        return {"success": True, "output": {"sources": [item.to_dict() for item in results]}}

    if tool.name.startswith("skill__"):
        skill_name = tool.name.removeprefix("skill__")
        if skill_name in ADMIN_ONLY_SKILLS and context.user_role != "admin":
            raise PermissionError("该 Skill 仅管理员可执行")
        registry = get_skill_registry()
        skill = registry.get_skill(skill_name)
        if skill is None:
            raise WorkflowToolError(f"Skill 不存在: {skill_name}")
        validation_error = skill.validate_params(arguments)
        if validation_error:
            raise WorkflowToolError(validation_error)
        result = await skill.execute(arguments, context)
        payload = result.to_dict()
        if not result.success:
            raise WorkflowToolError(result.error or "Skill 执行失败")
        return payload

    if tool.name.startswith("mcp__"):
        _, server_name, tool_name = tool.name.split("__", 2)
        from app.mcp.client import get_mcp_client

        result = await get_mcp_client().call_tool(server_name, tool_name, arguments)
        if not result.get("success") or result.get("is_error"):
            raise WorkflowToolError(result.get("error") or "MCP 工具执行失败")
        return result
    raise WorkflowToolError(f"不支持的工作流工具: {tool.name}")
