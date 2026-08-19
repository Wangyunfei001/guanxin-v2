"""技能注册表模块。

自动扫描 builtins/ 目录并注册所有内置技能。
"""

import importlib
import inspect
import pkgutil
from typing import Dict, List, Optional

from app.skills.base import BaseSkill


class SkillRegistry:
    """技能注册表。"""

    def __init__(self) -> None:
        self._skills: Dict[str, BaseSkill] = {}
        self._initialized: bool = False

    def register(self, skill: BaseSkill) -> None:
        """注册技能。"""
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
        """自动扫描并注册所有内置技能。"""
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
                                self.register(instance)
                            except Exception:
                                pass
                except Exception:
                    pass
        except Exception:
            pass

        self._initialized = True


# 全局单例
_skill_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    """获取全局技能注册表单例。"""
    global _skill_registry
    if _skill_registry is None:
        _skill_registry = SkillRegistry()
    return _skill_registry
