"""技能执行器模块。

负责技能的编排和执行，支持 DAG 依赖管理。
"""

from typing import Any, Dict, List

from app.models.skill import SkillResult
from app.models.skill_context import SkillContext
from app.skills.registry import get_skill_registry

ADMIN_ONLY_SKILLS = {
    "create_user",
    "update_user",
    "delete_user",
    "query_users",
    "export_data",
    "system_diagnosis",
}


class SkillExecutor:
    """技能执行器。"""

    def __init__(self) -> None:
        self.registry = get_skill_registry()

    def execute(
        self,
        skill_name: str,
        params: Dict[str, Any],
        context: SkillContext,
    ) -> SkillResult:
        """同步执行技能。

        Args:
            skill_name: 技能名称
            params: 参数字典
            context: 执行上下文

        Returns:
            SkillResult 执行结果
        """
        skill = self.registry.get_skill(skill_name)
        if skill is None:
            return SkillResult(
                success=False,
                error=f"技能 '{skill_name}' 未注册",
            )

        if skill_name in ADMIN_ONLY_SKILLS and context.user_role != "admin":
            return SkillResult(success=False, error="权限不足：该技能仅管理员可执行")

        # 校验参数
        error_msg = skill.validate_params(params)
        if error_msg:
            return SkillResult(success=False, error=error_msg)

        # 执行技能
        try:
            import asyncio

            # 检查是否在事件循环中
            try:
                loop = asyncio.get_running_loop()
                # 在事件循环中，创建新线程执行
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        skill.execute(params, context),
                    )
                    return future.result(timeout=30)
            except RuntimeError:
                # 不在事件循环中，直接运行
                return asyncio.run(skill.execute(params, context))
        except Exception as e:
            return SkillResult(success=False, error=f"技能执行失败: {str(e)}")

    def execute_chain(
        self,
        steps: List[Dict[str, Any]],
        context: SkillContext,
    ) -> List[SkillResult]:
        """按顺序执行多个技能（线性 DAG）。

        Args:
            steps: 执行步骤列表，每项包含 name 和 params
            context: 执行上下文

        Returns:
            SkillResult 列表
        """
        results: List[SkillResult] = []
        for step in steps:
            name = step.get("name", "")
            params = step.get("params", {})
            result = self.execute(name, params, context)
            results.append(result)
            if not result.success:
                break  # 某步失败则停止
        return results
