"""技能执行器模块。

负责技能的编排和执行，支持 DAG 依赖管理。
"""

import asyncio
import concurrent.futures
from typing import Any, Dict, List

from app.models.skill import SkillResult
from app.models.skill_context import SkillContext
from app.skills.registry import get_skill_registry

# 单个技能的最长执行时间。
SKILL_EXECUTION_TIMEOUT_SECONDS = 30

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

    def _resolve(
        self,
        skill_name: str,
        params: Dict[str, Any],
        context: SkillContext,
    ) -> tuple[Any, SkillResult | None]:
        """校验权限与参数，返回 (skill, 失败结果)。"""
        skill = self.registry.get_skill(skill_name)
        if skill is None:
            return None, SkillResult(
                success=False,
                error=f"技能 '{skill_name}' 未注册",
            )

        if skill_name in ADMIN_ONLY_SKILLS and context.user_role != "admin":
            return None, SkillResult(
                success=False, error="权限不足：该技能仅管理员可执行"
            )

        error_msg = skill.validate_params(params)
        if error_msg:
            return None, SkillResult(success=False, error=error_msg)

        return skill, None

    async def execute_async(
        self,
        skill_name: str,
        params: Dict[str, Any],
        context: SkillContext,
        timeout: float = SKILL_EXECUTION_TIMEOUT_SECONDS,
    ) -> SkillResult:
        """异步执行技能。

        超时是真的：到期立即返回，不会等技能跑完。路由层用这个方法，
        避免阻塞事件循环。
        """
        skill, failure = self._resolve(skill_name, params, context)
        if failure is not None:
            return failure
        try:
            return await asyncio.wait_for(
                skill.execute(params, context), timeout=timeout
            )
        except asyncio.TimeoutError:
            return SkillResult(
                success=False, error=f"技能执行超时（{timeout} 秒）"
            )
        except Exception as e:
            return SkillResult(success=False, error=f"技能执行失败: {str(e)}")

    def execute(
        self,
        skill_name: str,
        params: Dict[str, Any],
        context: SkillContext,
    ) -> SkillResult:
        """同步执行技能。

        仅供非事件循环环境使用。在事件循环里调用会放到独立线程，且超时
        是真的——不会因为等待线程收尾而超时失效。
        """
        skill, failure = self._resolve(skill_name, params, context)
        if failure is not None:
            return failure
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # 不在事件循环中，直接运行
            try:
                return asyncio.run(skill.execute(params, context))
            except Exception as e:
                return SkillResult(success=False, error=f"技能执行失败: {str(e)}")

        # 在事件循环中：不能同步等待异步技能。放到独立线程，超时后不等待
        # 线程收尾就返回。
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(asyncio.run, skill.execute(params, context))
            try:
                return future.result(timeout=SKILL_EXECUTION_TIMEOUT_SECONDS)
            except concurrent.futures.TimeoutError:
                return SkillResult(
                    success=False,
                    error=f"技能执行超时（{SKILL_EXECUTION_TIMEOUT_SECONDS} 秒）",
                )
        except Exception as e:
            return SkillResult(success=False, error=f"技能执行失败: {str(e)}")
        finally:
            executor.shutdown(wait=False)

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
