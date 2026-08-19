"""A2UI 模块初始化。"""

from app.a2ui.catalog import get_catalog, get_component_spec, validate_schema
from app.a2ui.templates import get_templates, get_template
from app.a2ui.renderer import render_for_agent, render_dynamic, generate_for_tool_result

__all__ = [
    "get_catalog",
    "get_component_spec",
    "validate_schema",
    "get_templates",
    "get_template",
    "render_for_agent",
    "render_dynamic",
    "generate_for_tool_result",
]
