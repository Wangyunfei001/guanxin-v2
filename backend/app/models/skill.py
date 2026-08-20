"""Skill 模型模块。"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class SkillType(str, Enum):
    """技能类型。"""

    BUILTIN = "builtin"
    CUSTOM = "custom"


class SkillStatus(str, Enum):
    """技能状态。"""

    ACTIVE = "active"
    INACTIVE = "inactive"


@dataclass
class SkillParam:
    """技能参数定义。"""

    name: str
    type: str  # string | number | boolean | array
    description: str
    required: bool = False
    default: Any = None
    options: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "required": self.required,
            "default": self.default,
            "options": self.options,
        }


@dataclass
class SkillMetadata:
    """技能元数据。"""

    name: str
    display_name: str
    description: str
    skill_type: SkillType = SkillType.BUILTIN
    status: SkillStatus = SkillStatus.ACTIVE
    version: str = "1.0.0"
    author: str = "system"
    params: List[SkillParam] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    category: str = "general"
    dependencies: List[str] = field(default_factory=list)
    effect: str = "read"  # read | write
    approval_required: bool = False
    idempotent: bool = True
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "skill_type": self.skill_type.value,
            "status": self.status.value,
            "version": self.version,
            "author": self.author,
            "params": [p.to_dict() for p in self.params],
            "tags": self.tags,
            "category": self.category,
            "dependencies": self.dependencies,
            "effect": self.effect,
            "approval_required": self.approval_required,
            "idempotent": self.idempotent,
            "created_at": self.created_at,
        }


@dataclass
class SkillResult:
    """技能执行结果。"""

    success: bool
    output: Any = None
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
        }
