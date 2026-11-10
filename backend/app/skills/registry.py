"""技能注册表模块。

自动扫描 builtins/ 目录并注册所有内置技能。
"""

import importlib
import inspect
import logging
import pkgutil
from typing import Dict, List, Optional

from app.models.skill import VALID_SKILL_EFFECTS
from app.skills.base import BaseSkill

logger = logging.getLogger(__name__)


class SkillRegistry:
    """技能注册表。"""

    def __init__(self) -> None:
        self._skills: Dict[str, BaseSkill] = {}
        self._initialized: bool = False

    def register(self, skill: BaseSkill) -> None:
        """注册技能。

        effect 非法的技能会被拒绝——副作用等级必须在注册时就确定，
        不能等到执行时才猜。
        """
        effect = getattr(skill.metadata, "effect", None)
        if effect not in VALID_SKILL_EFFECTS:
            logger.error(
                "技能 %s 的 effect 非法（%r），已拒绝注册；只允许 read / write / unknown",
                getattr(skill.metadata, "name", skill.__class__.__name__),
                effect,
            )
            return
        self._skills[skill.name] = skill

    def unregister(self, name: str) -> bool:
        """注销技能。"""
        if name in self._skills:
            del self._skills[name]
            return True
        return False

    def get_skill(self, name: str) -> Optional[BaseSkill]:
        """获取技能实例。"""
        return self._skills.get(name)

    def list_skills(self) -> List[BaseSkill]:
        """列出所有已注册技能。"""
        return list(self._skills.values())

    def list_metadata(self) -> List[dict]:
        """列出所有技能元数据。"""
        return [s.metadata.to_dict() for s in self._skills.values()]

    def register_all(self) -> None:
        """自动扫描并注册所有内置技能。

        注册失败的技能会被记录并跳过，而不是静默消失——一个坏掉的
        Skill 不应该让目录里“凭空少一项能力”且没有线索。
        """
        if self._initialized:
            return

        try:
            from app.skills import builtins as builtins_pkg

            for importer, modname, ispkg in pkgutil.iter_modules(
                builtins_pkg.__path__
            ):
                try:
                    module = importlib.import_module(
                        f"app.skills.builtins.{modname}"
                    )
                    for _name, obj in inspect.getmembers(module, inspect.isclass):
                        if (
                            issubclass(obj, BaseSkill)
                            and obj is not BaseSkill
                            and obj.__module__ == module.__name__
                        ):
                            try:
                                instance = obj()
                            except Exception:
                                logger.exception(
                                    "内置技能 %s 实例化失败，已跳过注册", obj.__name__
                                )
                                continue
                            self.register(instance)
                except Exception:
                    logger.exception("加载内置技能模块 %s 失败", modname)
        except Exception:
            logger.exception("扫描内置技能目录失败")

        self._initialized = True


# 全局单例
_skill_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    """获取全局技能注册表单例。"""
    global _skill_registry
    if _skill_registry is None:
        _skill_registry = SkillRegistry()
    return _skill_registry
