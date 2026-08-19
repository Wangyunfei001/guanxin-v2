"""查询用户列表技能。"""

from typing import Any, Dict

from app.models.skill import SkillMetadata, SkillParam, SkillResult, SkillType
from app.models.skill_context import SkillContext
from app.skills.base import BaseSkill
from app.services.user_store import query_users


class QueryUsersSkill(BaseSkill):
    def _define_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="query_users",
            display_name="查询用户列表",
            description="查询系统中的用户列表，支持关键词搜索、角色筛选和分页。",
            skill_type=SkillType.BUILTIN,
            params=[
                SkillParam(name="keyword", type="string", description="搜索关键词（匹配用户名或邮箱）", required=False),
                SkillParam(name="role", type="string", description="按角色筛选", required=False, options=["admin", "user", "viewer"]),
                SkillParam(name="page", type="number", description="页码", required=False, default=1),
                SkillParam(name="page_size", type="number", description="每页数量", required=False, default=10),
            ],
            tags=["用户管理", "查询"],
            category="user",
        )

    async def execute(self, params: Dict[str, Any], context: SkillContext) -> SkillResult:
        keyword = params.get("keyword", "")
        role = params.get("role", "")
        page = int(params.get("page", 1))
        page_size = int(params.get("page_size", 10))

        result = query_users(keyword=keyword, role=role, page=page, page_size=page_size)

        # Generate chart data from actual user list
        users = result.get("users", [])
        role_counts = {}
        status_counts = {}
        for u in users:
            r = u.get("role", "unknown")
            role_counts[r] = role_counts.get(r, 0) + 1
            s = u.get("status", "unknown")
            status_counts[s] = status_counts.get(s, 0) + 1

        return SkillResult(
            success=True,
            output={
                **result,
                "chart_data": {
                    "type": "pie",
                    "title": "角色分布",
                    "labels": list(role_counts.keys()),
                    "values": list(role_counts.values()),
                },
            },
        )