"""更新用户技能。"""

from typing import Any, Dict

from app.models.skill import SkillMetadata, SkillParam, SkillResult, SkillType
from app.models.skill_context import SkillContext
from app.skills.base import BaseSkill
from app.services.user_store import update_user


class UpdateUserSkill(BaseSkill):
    def _define_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="update_user",
            display_name="更新用户",
            description="更新系统中已存在用户的信息。需要用户ID(user_id)，可更新用户名(username)、邮箱(email)、角色(role)。",
            skill_type=SkillType.BUILTIN,
            params=[
                SkillParam(name="user_id", type="string", description="要更新的用户ID", required=True),
                SkillParam(name="username", type="string", description="新用户名（留空不修改）", required=False),
                SkillParam(name="email", type="string", description="新邮箱（留空不修改）", required=False),
                SkillParam(name="role", type="string", description="新角色", required=False, options=["admin", "user", "viewer"]),
            ],
            tags=["用户管理", "更新"],
            category="user",
        )

    async def execute(self, params: Dict[str, Any], context: SkillContext) -> SkillResult:
        user_id = params.get("user_id", "")
        if not user_id:
            return SkillResult(success=False, error="用户ID为必填项")

        updated = update_user(
            user_id=user_id,
            username=params.get("username"),
            email=params.get("email"),
            role=params.get("role"),
        )
        if updated is None:
            return SkillResult(success=False, error=f"用户 {user_id} 不存在")

        return SkillResult(
            success=True,
            output={**updated, "message": f"用户 {updated['username']} 更新成功"},
        )