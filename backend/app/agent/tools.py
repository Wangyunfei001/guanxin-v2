"""Agent 工具模块。

当前只保留知识库检索工具。Skill 与 MCP 工具统一由
``app.agent.tool_catalog`` 构造——那里是 Agent 可见能力的唯一来源，
同时负责租户隔离、RBAC 过滤与风险分级。
"""

from langchain_core.tools import tool

from app.core.tenant import get_tenant_id
from app.services.retrieval_service import get_retrieval_service


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
