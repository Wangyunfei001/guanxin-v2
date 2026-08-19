"""Agent 工具模块。

定义 Agent 可调用的工具，包括：
1. kb_retrieval — 知识库检索
2. skill__<skill_name> — 每个注册 Skill 的独立 tool
3. mcp__<server>__<tool_name> — 每个 MCP Server 暴露的工具
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

from app.core.tenant import get_tenant_id
from app.services.retrieval_service import get_retrieval_service

logger = logging.getLogger(__name__)

ADMIN_ONLY_SKILLS = {
    "create_user",
    "update_user",
    "delete_user",
    "query_users",
    "export_data",
    "system_diagnosis",
}


def get_tools_description(tools: List) -> str:
    """获取工具描述列表（用于系统提示词）。

    Args:
        tools: LangChain Tool 列表

    Returns:
        工具描述字符串
    """
    descriptions = []
    for t in tools:
        descriptions.append(f"- {t.name}: {t.description}")
    return "\n".join(descriptions)


def kb_retrieval_tool_factory():
    """创建知识库检索工具。

    使用工厂函数确保每次调用时获取最新的租户上下文。
    """

    @tool("kb_retrieval")
    def kb_retrieval(query: str) -> str:
        """检索知识库，找到与查询最相关的文档片段。

        Args:
            query: 查询文本

        Returns:
            检索结果文本
        """
        tenant_id = get_tenant_id()
        if not tenant_id:
            return "错误：无法确定租户上下文"

        service = get_retrieval_service()
        results = service.retrieve(query=query, tenant_id=tenant_id, top_k=5)

        if not results:
            return "未找到相关文档。"

        output_parts = []
        for i, r in enumerate(results, 1):
            output_parts.append(
                f"【片段 {i}】来源: {r.filename} | 相关度: {r.score:.2f}\n{r.content}"
            )
        return "\n\n".join(output_parts)

    return kb_retrieval


def skill_execute_tool_factory():
    """创建技能执行工具（保留兼容，新代码使用 skill__ 前缀的独立 tool）。"""

    @tool("skill_execute")
    def skill_execute(skill_name: str, params: str) -> str:
        """执行指定技能。

        Args:
            skill_name: 技能名称
            params: JSON 格式的参数字符串

        Returns:
            技能执行结果文本
        """
        from app.models.skill_context import SkillContext
        from app.skills.executor import SkillExecutor

        try:
            params_dict: Dict[str, Any] = json.loads(params) if params else {}
        except json.JSONDecodeError:
            return f"错误：参数 JSON 解析失败"

        tenant_id = get_tenant_id() or "default"
        context = SkillContext(
            tenant_id=tenant_id,
            user_id="system",
            conversation_id="",
        )

        executor = SkillExecutor()
        result = executor.execute(skill_name, params_dict, context)

        if result.success:
            return json.dumps(
                {"success": True, "output": result.output},
                ensure_ascii=False,
            )
        else:
            return json.dumps(
                {"success": False, "error": result.error},
                ensure_ascii=False,
            )

    return skill_execute


def _create_mcp_langchain_tool(server_name: str, mcp_tool: dict):
    """将 MCP 工具包装为 LangChain Tool。

    Args:
        server_name: MCP Server 名称
        mcp_tool: MCP 工具定义 dict（含 name, description, input_schema）

    Returns:
        LangChain Tool 对象，名称为 mcp__<server>__<tool_name>
    """
    tool_name = f"mcp__{server_name}__{mcp_tool['name']}"
    tool_description = mcp_tool.get("description", "") or f"MCP tool: {mcp_tool['name']}"

    @tool(tool_name)
    def mcp_tool_func(params: str) -> str:
        """调用 MCP Server 上的工具。

        Args:
            params: JSON 格式的参数字符串
        """
        try:
            arguments: Dict[str, Any] = json.loads(params) if params else {}
        except json.JSONDecodeError:
            return json.dumps(
                {"success": False, "error": "参数 JSON 解析失败"},
                ensure_ascii=False,
            )

        from app.mcp.client import get_mcp_client

        mcp_client = get_mcp_client()
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                mcp_client.call_tool(server_name, mcp_tool["name"], arguments)
            )
        finally:
            loop.close()

        return json.dumps(result, ensure_ascii=False)

    mcp_tool_func.description = tool_description
    return mcp_tool_func


def get_tools(
    enabled_names: Optional[List[str]] = None,
    include_skills: bool = True,
    include_mcp: bool = True,
    user_role: str = "admin",
) -> List:
    """获取 Agent 工具列表。

    Args:
        enabled_names: 用户配置启用的工具名列表，None=全部启用
        include_skills: 是否包含 Skill 工具
        include_mcp: 是否包含 MCP 工具

    Returns:
        LangChain Tool 对象列表，包含：
        1. kb_retrieval — 知识库检索
        2. skill__<skill_name> — 每个注册 Skill 的独立 tool
        3. mcp__<server>__<tool_name> — 每个 MCP Server 暴露的工具
    """
    tools: List = [kb_retrieval_tool_factory()]

    # 注册 Skill 工具（每个 Skill 独立 tool，前缀 skill__）
    if include_skills:
        try:
            from app.skills.registry import get_skill_registry

            registry = get_skill_registry()
            registry.register_all()
            for skill in registry.list_skills():
                if user_role != "admin" and skill.name in ADMIN_ONLY_SKILLS:
                    continue
                try:
                    tools.append(skill.as_langchain_tool())
                except Exception as e:
                    logger.warning("Failed to register skill tool %s: %s", skill.name, e)
        except Exception as e:
            logger.warning("Failed to load skill tools: %s", e)

    # 注册 MCP 工具（前缀 mcp__<server>__）
    if include_mcp:
        try:
            from app.mcp.client import get_mcp_client

            mcp_client = get_mcp_client()
            for server_name, conn in mcp_client._connections.items():
                for mcp_tool in conn.get("tools", []):
                    try:
                        tools.append(
                            _create_mcp_langchain_tool(server_name, mcp_tool)
                        )
                    except Exception as e:
                        logger.warning(
                            "Failed to register MCP tool %s/%s: %s",
                            server_name,
                            mcp_tool.get("name"),
                            e,
                        )
        except Exception as e:
            logger.warning("Failed to load MCP tools: %s", e)

    # 按名称过滤
    if enabled_names:
        tools = [t for t in tools if t.name in enabled_names]

    return tools


def get_enabled_tools(enabled_names: List[str], user_role: str = "admin") -> List:
    """根据名称列表过滤启用工具（兼容旧接口）。

    Args:
        enabled_names: 启用的工具名称列表

    Returns:
        过滤后的 Tool 列表
    """
    return get_tools(enabled_names=enabled_names or None, user_role=user_role)
