"""Skill 模型补充：SkillContext。"""

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class SkillContext:
    """技能执行上下文。"""

    tenant_id: str
    user_id: str
    user_role: str = "user"
    conversation_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
