"""A2UI 模板模块。

预定义常用场景的 A2UI Schema 模板。
"""

from typing import Any, Dict, List


def kb_result_template(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """知识库检索结果模板。

    Args:
        results: 检索结果列表

    Returns:
        ListCard Schema
    """
    columns = [
        {"key": "content", "label": "内容片段", "width": "50%"},
        {"key": "filename", "label": "来源文档", "width": "25%"},
        {"key": "score", "label": "相关度", "width": "25%"},
    ]

    rows = []
    for r in results:
        content = r.get("content", "")
        if len(content) > 100:
            content = content[:100] + "..."
        rows.append({
            "content": content,
            "filename": r.get("filename", "未知"),
            "score": f"{r.get('score', 0):.2f}",
        })

    return {
        "component_type": "list_card",
        "props": {
            "title": f"知识库检索结果（{len(rows)} 条）",
            "columns": columns,
            "rows": rows,
            "show_score": True,
        },
    }


def skill_result_template(
    skill_name: str,
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """技能执行结果模板。

    Args:
        skill_name: 技能名称
        result: 执行结果

    Returns:
        InfoCard Schema
    """
    items = []
    output = result.get("output", result)
    if isinstance(output, dict):
        for k, v in output.items():
            items.append({"label": k, "value": str(v)})
    else:
        items.append({"label": "结果", "value": str(output)})

    return {
        "component_type": "info_card",
        "props": {
            "title": f"技能执行结果：{skill_name}",
            "content": "执行成功" if result.get("success", True) else f"执行失败: {result.get('error', '')}",
            "items": items,
        },
    }


def confirm_action_template(
    title: str,
    message: str,
    danger: bool = False,
) -> Dict[str, Any]:
    """确认操作模板。

    Args:
        title: 确认标题
        message: 确认消息
        danger: 是否为危险操作

    Returns:
        ConfirmCard Schema
    """
    return {
        "component_type": "confirm_card",
        "props": {
            "title": title,
            "message": message,
            "confirm_text": "确认",
            "cancel_text": "取消",
            "danger": danger,
        },
    }


def data_analysis_template(
    title: str,
    stats: Dict[str, Any],
    chart_data: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """数据分析结果模板。

    Args:
        title: 标题
        stats: 统计数据
        chart_data: 图表数据

    Returns:
        InfoCard + ChartCard 组合 Schema
    """
    items = []
    for k, v in stats.items():
        if k != "chart_data" and k != "sorted":
            items.append({"label": k, "value": str(v)})

    children = []
    if chart_data:
        children.append({
            "component_type": "chart_card",
            "props": {
                "title": "数据可视化",
                "chart_type": chart_data.get("type", "bar"),
                "labels": chart_data.get("labels", []),
                "values": chart_data.get("values", []),
            },
        })

    return {
        "component_type": "info_card",
        "props": {
            "title": title,
            "content": "数据分析结果",
            "items": items,
        },
        "children": children,
    }


def error_card_template(title: str, message: str) -> Dict[str, Any]:
    """错误信息模板。

    Args:
        title: 错误标题
        message: 错误消息

    Returns:
        InfoCard Schema
    """
    return {
        "component_type": "info_card",
        "props": {
            "title": f"❌ {title}",
            "content": message,
            "items": [],
        },
    }


# === 模板注册表 ===
TEMPLATES: Dict[str, Any] = {
    "kb_result": kb_result_template,
    "skill_result": skill_result_template,
    "confirm_action": confirm_action_template,
    "data_analysis": data_analysis_template,
    "error": error_card_template,
}


def get_templates() -> List[dict]:
    """获取所有模板列表。"""
    return [
        {"name": name, "description": func.__doc__ or ""}
        for name, func in TEMPLATES.items()
    ]


def get_template(name: str):
    """获取指定模板函数。"""
    return TEMPLATES.get(name)
