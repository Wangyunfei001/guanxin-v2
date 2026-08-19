"""导出数据技能。"""

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any, Dict

from app.models.skill import SkillMetadata, SkillParam, SkillResult, SkillType
from app.models.skill_context import SkillContext
from app.skills.base import BaseSkill
from app.services.user_store import query_users


class ExportDataSkill(BaseSkill):
    def _define_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="export_data",
            display_name="导出数据",
            description="将系统中的用户数据导出为指定格式的文件。",
            skill_type=SkillType.BUILTIN,
            params=[
                SkillParam(name="data_type", type="string", description="数据类型", required=True, options=["users", "logs", "reports"]),
                SkillParam(name="format", type="string", description="导出格式", required=False, default="csv", options=["csv", "json", "xlsx"]),
                SkillParam(name="date_range", type="string", description="日期范围（如 2025-01-01~2025-12-31）", required=False),
            ],
            tags=["数据", "导出"],
            category="data",
        )

    async def execute(self, params: Dict[str, Any], context: SkillContext) -> SkillResult:
        data_type = params.get("data_type", "users")
        export_format = params.get("format", "csv")

        if data_type == "users":
            result = query_users(page_size=1000)
            users = result.get("users", [])
            record_count = len(users)

            if export_format == "csv":
                output_buf = io.StringIO()
                writer = csv.DictWriter(output_buf, fieldnames=["user_id", "username", "email", "role", "status", "created_at"])
                writer.writeheader()
                for u in users:
                    writer.writerow({k: u.get(k, "") for k in writer.fieldnames})
                preview = output_buf.getvalue()[:500]
            elif export_format == "json":
                preview = json.dumps(users, ensure_ascii=False, indent=2)[:500]
            else:
                preview = f"XLSX export of {record_count} records"

            return SkillResult(
                success=True,
                output={
                    "data_type": data_type,
                    "format": export_format,
                    "record_count": record_count,
                    "file_size": f"{len(preview.encode('utf-8')) * 10} bytes (estimated)",
                    "preview": preview,
                    "exported_at": datetime.now(timezone.utc).isoformat(),
                    "message": f"成功导出 {record_count} 条用户数据",
                },
            )

        return SkillResult(success=False, error=f"不支持的数据类型: {data_type}")