"""Skill API 模块。

提供技能列表、执行等接口。
"""

import json
from typing import Any, Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.deps import get_current_user
from app.core.responses import success
from app.core.tenant import get_tenant_id
from app.models.skill_context import SkillContext
from app.models.tenant import User
from app.skills.executor import ADMIN_ONLY_SKILLS, SkillExecutor
from app.skills.registry import get_skill_registry

router = APIRouter(prefix="/skills", tags=["技能"])


@router.get("")
async def list_skills(user: User = Depends(get_current_user)):
    """列出所有已注册技能。"""
    registry = get_skill_registry()
    skills = registry.list_metadata()
    if user.role != "admin":
        skills = [item for item in skills if item["name"] not in ADMIN_ONLY_SKILLS]
    return success(skills)


@router.get("/{skill_name}")
async def get_skill_detail(
    skill_name: str,
    user: User = Depends(get_current_user),
):
    """获取技能详情。"""
    registry = get_skill_registry()
    skill = registry.get_skill(skill_name)
    if skill is None or (user.role != "admin" and skill_name in ADMIN_ONLY_SKILLS):
        return {"code": 4041, "message": "技能未找到", "data": None}
    return success(skill.metadata.to_dict())


class ExecuteSkillRequest(BaseModel):
    """执行技能请求。"""

    skill_name: str
    params: Dict[str, Any] = {}


@router.post("/execute")
async def execute_skill(
    request: ExecuteSkillRequest,
    user: User = Depends(get_current_user),
):
    """执行技能。"""
    tenant_id = get_tenant_id() or user.tenant_id
    context = SkillContext(
        tenant_id=tenant_id,
        user_id=user.user_id,
        user_role=user.role,
    )
    executor = SkillExecutor()
    result = executor.execute(request.skill_name, request.params, context)
    return success(result.to_dict())
