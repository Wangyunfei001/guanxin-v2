"""A2UI 组件目录模块。

定义所有可用的 A2UI 组件类型及其 Schema 规范。
"""

from typing import Any, Dict, List, Optional

# === 组件类型常量 ===
COMPONENT_TYPE_FORM = "form_card"
COMPONENT_TYPE_INFO = "info_card"
COMPONENT_TYPE_LIST = "list_card"
COMPONENT_TYPE_CONFIRM = "confirm_card"
COMPONENT_TYPE_CHART = "chart_card"


# === 组件 Schema 规范 ===
COMPONENT_CATALOG: Dict[str, dict] = {
    COMPONENT_TYPE_FORM: {
        "component_type": COMPONENT_TYPE_FORM,
        "display_name": "表单卡片",
        "description": "包含输入字段的表单卡片，支持文本、选择、数字等字段类型",
        "props_schema": {
            "title": {"type": "string", "description": "表单标题"},
            "fields": {
                "type": "array",
                "description": "表单字段列表",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "字段名"},
                        "label": {"type": "string", "description": "字段标签"},
                        "type": {
                            "type": "string",
                            "enum": ["input", "select", "textarea", "number", "switch"],
                            "description": "字段类型",
                        },
                        "value": {"type": "any", "description": "默认值"},
                        "options": {"type": "array", "description": "select 类型的选项"},
                        "required": {"type": "boolean", "description": "是否必填"},
                    },
                },
            },
            "submit_text": {"type": "string", "description": "提交按钮文本"},
        },
    },
    COMPONENT_TYPE_INFO: {
        "component_type": COMPONENT_TYPE_INFO,
        "display_name": "信息卡片",
        "description": "展示键值对信息的卡片，适合展示结构化数据",
        "props_schema": {
            "title": {"type": "string", "description": "卡片标题"},
            "content": {"type": "string", "description": "主要内容文本"},
            "items": {
                "type": "array",
                "description": "键值对列表",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string", "description": "键名"},
                        "value": {"type": "any", "description": "值"},
                    },
                },
            },
        },
    },
    COMPONENT_TYPE_LIST: {
        "component_type": COMPONENT_TYPE_LIST,
        "display_name": "列表卡片",
        "description": "以表格形式展示列表数据，适合检索结果",
        "props_schema": {
            "title": {"type": "string", "description": "列表标题"},
            "columns": {
                "type": "array",
                "description": "列定义",
                "items": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "数据字段名"},
                        "label": {"type": "string", "description": "列标题"},
                        "width": {"type": "string", "description": "列宽"},
                    },
                },
            },
            "rows": {
                "type": "array",
                "description": "数据行",
                "items": {"type": "object"},
            },
            "show_score": {"type": "boolean", "description": "是否显示分数列"},
        },
    },
    COMPONENT_TYPE_CONFIRM: {
        "component_type": COMPONENT_TYPE_CONFIRM,
        "display_name": "确认卡片",
        "description": "需要用户确认的操作卡片",
        "props_schema": {
            "title": {"type": "string", "description": "确认标题"},
            "message": {"type": "string", "description": "确认消息"},
            "confirm_text": {"type": "string", "description": "确认按钮文本"},
            "cancel_text": {"type": "string", "description": "取消按钮文本"},
            "danger": {"type": "boolean", "description": "是否为危险操作"},
        },
    },
    COMPONENT_TYPE_CHART: {
        "component_type": COMPONENT_TYPE_CHART,
        "display_name": "图表卡片",
        "description": "数据可视化卡片，支持柱状图和折线图",
        "props_schema": {
            "title": {"type": "string", "description": "图表标题"},
            "chart_type": {
                "type": "string",
                "enum": ["bar", "line"],
                "description": "图表类型",
            },
            "labels": {"type": "array", "description": "X 轴标签"},
            "values": {"type": "array", "description": "数据值"},
            "x_label": {"type": "string", "description": "X 轴名称"},
            "y_label": {"type": "string", "description": "Y 轴名称"},
        },
    },
}


def get_catalog() -> List[dict]:
    """获取所有组件类型目录。"""
    return list(COMPONENT_CATALOG.values())


def get_component_spec(component_type: str) -> Optional[dict]:
    """获取指定组件类型的 Schema 规范。"""
    return COMPONENT_CATALOG.get(component_type)


def validate_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """校验 A2UI Schema。

    Args:
        schema: 待校验的 A2UI Schema

    Returns:
        {"valid": bool, "errors": list}
    """
    errors: List[str] = []

    if not isinstance(schema, dict):
        return {"valid": False, "errors": ["Schema 必须是对象"]}

    component_type = schema.get("component_type")
    if not component_type:
        errors.append("缺少 component_type 字段")
        return {"valid": False, "errors": errors}

    spec = COMPONENT_CATALOG.get(component_type)
    if not spec:
        errors.append(f"未知的组件类型: {component_type}")
        return {"valid": False, "errors": errors}

    # 校验 props
    props = schema.get("props", {})
    if not isinstance(props, dict):
        errors.append("props 必须是对象")

    # 校验 children（如果存在）
    children = schema.get("children")
    if children is not None:
        if not isinstance(children, list):
            errors.append("children 必须是数组")
        else:
            for i, child in enumerate(children):
                child_result = validate_schema(child)
                if not child_result["valid"]:
                    errors.append(f"children[{i}]: {child_result['errors']}")

    return {"valid": len(errors) == 0, "errors": errors}
