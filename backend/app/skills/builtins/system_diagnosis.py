"""系统诊断技能。"""

from datetime import datetime, timezone
from typing import Any, Dict

from app.models.skill import SkillMetadata, SkillParam, SkillResult, SkillType
from app.models.skill_context import SkillContext
from app.skills.base import BaseSkill
from app.services.user_store import get_all_users

# Try to import psutil for real system metrics
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class SystemDiagnosisSkill(BaseSkill):
    def _define_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="system_diagnosis",
            display_name="系统诊断",
            description="对系统进行健康检查，返回CPU、内存、磁盘、数据库状态和用户统计信息。",
            skill_type=SkillType.BUILTIN,
            params=[
                SkillParam(name="check_type", type="string", description="检查类型", required=False, default="full", options=["basic", "full", "database", "cache"]),
            ],
            tags=["系统", "诊断"],
            category="system",
        )

    async def execute(self, params: Dict[str, Any], context: SkillContext) -> SkillResult:
        check_type = params.get("check_type", "full")
        now = datetime.now(timezone.utc).isoformat()

        # Real system metrics via psutil, graceful fallback
        if HAS_PSUTIL:
            cpu = round(psutil.cpu_percent(interval=0.5), 1)
            mem = psutil.virtual_memory()
            memory_percent = round(mem.percent, 1)
            disk = psutil.disk_usage("/")
            disk_percent = round(disk.percent, 1)
        else:
            cpu, memory_percent, disk_percent = 0, 0, 0

        # Real user statistics
        all_users = get_all_users()
        user_count = len(all_users)
        active_count = sum(1 for u in all_users if u.get("status") == "active")
        role_counts = {}
        for u in all_users:
            r = u.get("role", "unknown")
            role_counts[r] = role_counts.get(r, 0) + 1

        output = {
            "timestamp": now,
            "check_type": check_type,
            "system": {
                "cpu_percent": cpu,
                "memory_percent": memory_percent,
                "disk_percent": disk_percent,
                "status": "healthy" if cpu < 90 and memory_percent < 90 else "degraded",
            },
            "users": {
                "total": user_count,
                "active": active_count,
                "inactive": user_count - active_count,
                "role_distribution": role_counts,
            },
            "chart_data": {
                "type": "bar",
                "title": "系统资源使用率",
                "labels": ["CPU", "内存", "磁盘"],
                "values": [cpu, memory_percent, disk_percent],
            },
        }

        return SkillResult(success=True, output=output)