"""删除用户技能。"""

from typing import Any, Dict

from app.models.skill import SkillMetadata, SkillParam, SkillResult, SkillType
from app.models.skill_context import SkillContext
from app.skills.base import BaseSkill
from app.services.user_store import delete_user


class DeleteUserSkill(BaseSkill):
    def _define_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="delete_user",
            display_name="删除用户",
            description="从系统中删除一个用户。此操作不可逆，请谨慎使用。",
            skill_type=SkillType.BUILTIN,
            params=[
                SkillParam(name="user_id", type="string", description="要删除的用户ID", required=True),
            ],
            tags=["用户管理", "删除"],
            category="user",
        )

    async def execute(self, params: Dict[str, Any], context: SkillContext) -> SkillResult:
        user_id = params.get("user_id", "")
        if not user_id:
            return SkillResult(success=False, error="用户ID为必填项")

        ok = delete_user(user_id)
        if not ok:
            return SkillResult(success=False, error=f"用户 {user_id} 不存在")

        return SkillResult(
            success=True,
            output={"user_id": user_id, "message": "用户已删除", "danger": True},
        )