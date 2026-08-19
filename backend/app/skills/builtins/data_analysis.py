"""数据分析技能。"""

import json
from typing import Any, Dict, List

from app.models.skill import SkillMetadata, SkillParam, SkillResult, SkillType
from app.models.skill_context import SkillContext
from app.skills.base import BaseSkill


class DataAnalysisSkill(BaseSkill):
    """数据分析技能：对数据进行基本统计分析。"""

    def _define_metadata(self) -> SkillMetadata:
        """定义技能元数据。"""
        return SkillMetadata(
            name="data_analysis",
            display_name="数据分析",
            description="对输入的数值数组进行基本统计分析，包括均值、中位数、最大值、最小值、标准差等。",
            skill_type=SkillType.BUILTIN,
            params=[
                SkillParam(
                    name="data",
                    type="array",
                    description="数值数组，如 [1, 2, 3, 4, 5]",
                    required=True,
                ),
                SkillParam(
                    name="analysis_type",
                    type="string",
                    description="分析类型：basic（基本统计）/ full（完整分析含图表数据）",
                    required=False,
                    default="basic",
                    options=["basic", "full"],
                ),
            ],
            tags=["数据分析", "统计"],
            category="data",
        )

    async def execute(
        self,
        params: Dict[str, Any],
        context: SkillContext,
    ) -> SkillResult:
        """执行数据分析。"""
        data: List[float] = params.get("data", [])
        analysis_type: str = params.get("analysis_type", "basic")

        if not data:
            return SkillResult(success=False, error="数据为空")

        try:
            numbers = [float(x) for x in data]
        except (ValueError, TypeError):
            return SkillResult(success=False, error="数据包含非数值元素")

        n = len(numbers)
        mean_val = sum(numbers) / n
        sorted_nums = sorted(numbers)
        median_val = (
            sorted_nums[n // 2]
            if n % 2 == 1
            else (sorted_nums[n // 2 - 1] + sorted_nums[n // 2]) / 2
        )
        max_val = max(numbers)
        min_val = min(numbers)
        variance = sum((x - mean_val) ** 2 for x in numbers) / n
        std_val = variance ** 0.5

        result: Dict[str, Any] = {
            "count": n,
            "mean": round(mean_val, 4),
            "median": round(median_val, 4),
            "max": max_val,
            "min": min_val,
            "std": round(std_val, 4),
        }

        if analysis_type == "full":
            result["chart_data"] = {
                "type": "bar",
                "labels": [f"第{i+1}项" for i in range(n)],
                "values": numbers,
            }
            result["sorted"] = sorted_nums

        return SkillResult(
            success=True,
            output=result,
            metadata={"skill": "data_analysis", "analysis_type": analysis_type},
        )
