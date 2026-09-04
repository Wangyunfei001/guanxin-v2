"""A2UI 渲染器模块。

负责根据模板和数据生成 A2UI Schema，
以及根据工具调用结果自动生成 A2UI。
"""

import json
from typing import Any, Dict, List, Optional

from app.a2ui.catalog import (
    COMPONENT_TYPE_CHART,
    COMPONENT_TYPE_CONFIRM,
    COMPONENT_TYPE_FORM,
    COMPONENT_TYPE_INFO,
    COMPONENT_TYPE_LIST,
    validate_schema,
)
from app.a2ui.templates import TEMPLATES, get_template


def render_for_agent(template_name: str, data: Any) -> Optional[Dict[str, Any]]:
    """使用预定义模板渲染 A2UI Schema。

    Args:
        template_name: 模板名称
        data: 渲染数据

    Returns:
        A2UI Schema 字典，模板不存在返回 None
    """
    template_func = get_template(template_name)
    if template_func is None:
        return None

    try:
        if isinstance(data, dict):
            schema = template_func(**data)
        elif isinstance(data, list):
            schema = template_func(data)
        else:
            schema = template_func(data)
        return schema
    except Exception:
        return None


def render_dynamic(
    component_type: str,
    title: str,
    props: Dict[str, Any],
    children: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """动态构建 A2UI Schema。

    Args:
        component_type: 组件类型
        title: 标题
        props: 属性字典
        children: 子组件列表

    Returns:
        A2UI Schema 字典
    """
    schema: Dict[str, Any] = {
        "component_type": component_type,
        "props": {**props, "title": title},
    }
    if children:
        schema["children"] = children
    return schema


def generate_for_tool_result(
    tool_name: str,
    tool_input: Dict[str, Any],
    tool_output: str,
) -> Optional[Dict[str, Any]]:
    """根据工具调用结果自动生成 A2UI Schema。

    Args:
        tool_name: 工具名称
        tool_input: 工具输入参数
        tool_output: 工具输出文本

    Returns:
        A2UI Schema 字典，无法生成返回 None
    """
    if tool_name == "kb_retrieval":
        return _generate_kb_result_a2ui(tool_output)
    elif tool_name == "skill_execute":
        return _generate_skill_result_a2ui(tool_input, tool_output)
    elif tool_name.startswith("skill__"):
        return _generate_skill_result_a2ui(
            {**tool_input, "skill_name": tool_name.removeprefix("skill__")},
            tool_output,
        )
    else:
        # 通用信息卡片
        return _generate_generic_info_a2ui(tool_name, tool_input, tool_output)


def _generate_kb_result_a2ui(output: str) -> Optional[Dict[str, Any]]:
    """从知识库检索结果生成 ListCard。"""
    try:
        decoded = json.loads(output)
        if isinstance(decoded, str):
            output = decoded
    except (json.JSONDecodeError, TypeError):
        pass
    results = _parse_kb_results(output)
    if not results:
        return None

    template_func = get_template("kb_result")
    if template_func:
        return template_func(results)
    return None


def _generate_skill_result_a2ui(
    tool_input: Dict[str, Any],
    tool_output: str,
) -> Optional[Dict[str, Any]]:
    """从技能执行结果生成 InfoCard。"""
    skill_name = tool_input.get("skill_name", "未知技能")

    try:
        result = json.loads(tool_output)
    except (json.JSONDecodeError, TypeError):
        result = {"success": True, "output": tool_output}

    # 检查是否包含图表数据
    output = result.get("output", result)
    if isinstance(output, dict) and "chart_data" in output:
        template_func = get_template("data_analysis")
        if template_func:
            return template_func(
                title=f"技能执行结果：{skill_name}",
                stats=output,
                chart_data=output.get("chart_data"),
            )

    template_func = get_template("skill_result")
    if template_func:
        return template_func(skill_name, result)
    return None


def _generate_generic_info_a2ui(
    tool_name: str,
    tool_input: Dict[str, Any],
    tool_output: str,
) -> Dict[str, Any]:
    """生成通用信息卡片。"""
    items = []
    for k, v in tool_input.items():
        items.append({"label": k, "value": str(v)[:100]})

    output_display = tool_output[:500] if len(tool_output) > 500 else tool_output

    return {
        "component_type": COMPONENT_TYPE_INFO,
        "props": {
            "title": f"工具调用结果：{tool_name}",
            "content": output_display,
            "items": items,
        },
    }


def _parse_kb_results(output: str) -> List[Dict[str, Any]]:
    """解析知识库检索结果文本。

    输入格式示例：
    【片段 1】来源: doc.txt | 相关度: 0.85
    文档内容...

    【片段 2】来源: doc2.txt | 相关度: 0.72
    文档内容...
    """
    results: List[Dict[str, Any]] = []
    if not output or output.startswith("未找到") or output.startswith("错误"):
        return results

    # 按【片段 N】分割
    import re

    parts = re.split(r"【片段\s*\d+】", output)
    for part in parts:
        part = part.strip()
        if not part:
            continue

        # 解析来源和相关度
        filename = "未知"
        score = 0.0
        content = part

        header_match = re.match(
            r"来源:\s*(.+?)\s*\|\s*相关度:\s*([\d.]+)",
            part,
        )
        if header_match:
            filename = header_match.group(1).strip()
            score = float(header_match.group(2))
            content = part[header_match.end():].strip()

        results.append({
            "content": content[:200],
            "filename": filename,
            "score": score,
        })

    return results
