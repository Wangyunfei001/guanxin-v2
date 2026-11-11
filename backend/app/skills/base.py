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
