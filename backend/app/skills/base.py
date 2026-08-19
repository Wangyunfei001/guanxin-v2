"""技能基类模块。

定义 BaseSkill 抽象基类，所有内置和自定义技能都继承此类。
"""

import json
from abc import ABC, abstractmethod
from typing import Any, Dict

from app.models.skill import SkillMetadata, SkillResult
from app.models.skill_context import SkillContext


class BaseSkill(ABC):
    """技能抽象基类。

    所有技能必须实现 execute 方法。
    """

    def __init__(self) -> None:
        self._metadata: SkillMetadata = self._define_metadata()

    @abstractmethod
    def _define_metadata(self) -> SkillMetadata:
        """定义技能元数据。子类必须实现。"""
        ...

    @abstractmethod
    async def execute(
        self,
        params: Dict[str, Any],
        context: SkillContext,
    ) -> SkillResult:
        """执行技能。

        Args:
            params: 参数字典
            context: 执行上下文

        Returns:
            SkillResult 执行结果
        """
        ...

    @property
    def metadata(self) -> SkillMetadata:
        """获取技能元数据。"""
        return self._metadata

    @property
    def name(self) -> str:
        """获取技能名称。"""
        return self._metadata.name

    def validate_params(self, params: Dict[str, Any]) -> str:
        """校验参数。

        Args:
            params: 参数字典

        Returns:
            错误信息，为空表示校验通过
        """
        for param in self._metadata.params:
            if param.required and param.name not in params:
                return f"缺少必填参数: {param.name}"
        return ""

    def to_dict(self) -> dict:
        """转换为字典。"""
        return self._metadata.to_dict()

    def as_langchain_tool(self):
        """将 Skill 转为 LangChain Tool 对象。

        tool_name 格式: skill__<skill_name>
        tool_description: skill 的 description 字段
        tool_function: 封装 execute() 调用，接受 JSON 格式的 params 字符串

        Returns:
            LangChain Tool 对象
        """
        from langchain_core.tools import tool

        skill_name = self._metadata.name
        skill_description = self._metadata.description
        tool_name = f"skill__{skill_name}"

        # 构建 tool description 包含参数说明
        param_desc_parts = []
        for param in self._metadata.params:
            required_tag = "必填" if param.required else "可选"
            param_desc_parts.append(
                f"  - {param.name} ({param.type}, {required_tag}): {param.description}"
            )
        full_description = skill_description
        if param_desc_parts:
            full_description += "\n参数:\n" + "\n".join(param_desc_parts)
            full_description += '\n\n请以 JSON 字符串传入参数，如: {"param1": "value1"}'

        skill_instance = self

        @tool(tool_name)
        def skill_tool(params: str) -> str:
            """执行技能。

            Args:
                params: JSON 格式的参数字符串
            """
            import asyncio

            try:
                params_dict: Dict[str, Any] = json.loads(params) if params else {}
            except json.JSONDecodeError:
                return json.dumps(
                    {"success": False, "error": "参数 JSON 解析失败"},
                    ensure_ascii=False,
                )

            # 校验参数
            error = skill_instance.validate_params(params_dict)
            if error:
                return json.dumps(
                    {"success": False, "error": error},
                    ensure_ascii=False,
                )

            from app.core.tenant import get_tenant_id, get_user_id, get_user_role

            tenant_id = get_tenant_id() or "default"
            context = SkillContext(
                tenant_id=tenant_id,
                user_id=get_user_id() or "system",
                user_role=get_user_role() or "user",
                conversation_id="",
            )

            # execute 是 async 方法，在同步 tool 中运行
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    skill_instance.execute(params_dict, context)
                )
            finally:
                loop.close()

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

        # 覆盖 description
        skill_tool.description = full_description

        return skill_tool
