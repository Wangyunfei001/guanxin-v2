"""创建用户技能。"""

from datetime import datetime, timezone
from typing import Any, Dict

from app.models.skill import SkillMetadata, SkillParam, SkillResult, SkillType
from app.models.skill_context import SkillContext
from app.skills.base import BaseSkill
from app.services.user_store import create_user, query_users


class CreateUserSkill(BaseSkill):
    def _define_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="create_user",
            display_name="创建用户",
            description="在系统中创建一个新用户。需要提供用户名(username)、邮箱(email)和可选的用户角色(role)。",
            skill_type=SkillType.BUILTIN,
            params=[
                SkillParam(name="username", type="string", description="用户名（登录名）", required=True),
                SkillParam(name="email", type="string", description="邮箱地址", required=True),
                SkillParam(name="role", type="string", description="角色（admin/user/viewer）", required=False, default="user", options=["admin", "user", "viewer"]),
            ],
            tags=["用户管理", "创建"],
            category="user",
            effect="write",
            approval_required=True,
            idempotent=False,
        )

    async def execute(self, params: Dict[str, Any], context: SkillContext) -> SkillResult:
        username = params.get("username", "")
        email = params.get("email", "")
        role = params.get("role", "user")

        if not username or not email:
            return SkillResult(success=False, error="用户名和邮箱为必填项")

        try:
            user = create_user(username=username, email=email, role=role)
            # Chart data comes from the full filtered set, not from the current page.
            role_counts = query_users().get("statistics", {}).get("roles", {})
            return SkillResult(
                success=True,
                output={
                    **user,
                    "message": f"用户 {username} 创建成功",
                    "chart_data": {
                        "type": "bar",
                        "title": "用户角色分布",
                        "labels": list(role_counts.keys()),
                        "values": list(role_counts.values()),
                    },
                },
            )
        except Exception as e:
            return SkillResult(success=False, error=str(e))
