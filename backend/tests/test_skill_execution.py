"""技能执行器的阻塞与超时行为。"""

import asyncio
import time

import pytest

from app.models.skill import SkillMetadata, SkillResult
from app.models.skill_context import SkillContext
from app.skills.base import BaseSkill
from app.skills.executor import SkillExecutor
from app.skills.registry import SkillRegistry


class SlowSkill(BaseSkill):
    """一个故意很慢的技能。"""

    def __init__(self, name: str = "slow_test_skill") -> None:
        self._name = name
        super().__init__()

    def _define_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name=self._name,
            display_name="慢技能",
            description="测试用",
            effect="read",
        )

    async def execute(self, params, context) -> SkillResult:
        await asyncio.sleep(0.5)
        return SkillResult(success=True, output={"ok": True})


def _executor() -> SkillExecutor:
    registry = SkillRegistry()
    registry.register(SlowSkill())
    executor = SkillExecutor()
    executor.registry = registry
    return executor


def _context() -> SkillContext:
    return SkillContext(
        tenant_id="tenant-a",
        user_id="admin-001",
        user_role="admin",
        conversation_id="",
    )


class TestSkillExecution:
    """技能执行。"""

    @pytest.mark.asyncio
    async def test_execution_does_not_block_the_event_loop(self):
        """执行期间事件循环仍然可用。"""
        executor = _executor()
        marker: list[str] = []
        loop = asyncio.get_running_loop()

        task = asyncio.create_task(
            executor.execute_async("slow_test_skill", {}, _context())
        )
        loop.call_soon(marker.append, "scheduled")
        result = await task

        assert marker == ["scheduled"], "技能执行期间事件循环被阻塞了"
        assert result.success is True

    @pytest.mark.asyncio
    async def test_timeout_is_real(self):
        """超时立即返回，不等技能跑完。"""
        executor = _executor()
        started = time.monotonic()
        result = await executor.execute_async(
            "slow_test_skill", {}, _context(), timeout=0.05
        )
        elapsed = time.monotonic() - started

        assert result.success is False
        assert "超时" in result.error
        assert elapsed < 0.4, f"超时后仍在等待技能结束（{elapsed:.2f}s）"

    @pytest.mark.asyncio
    async def test_permission_is_checked_before_execution(self):
        """管理员专属技能对普通用户拒绝，且不进入执行。"""
        registry = SkillRegistry()
        registry.register(SlowSkill("create_user"))
        executor = SkillExecutor()
        executor.registry = registry

        context = SkillContext(
            tenant_id="tenant-a",
            user_id="user-001",
            user_role="user",
            conversation_id="",
        )
        started = time.monotonic()
        result = await executor.execute_async("create_user", {}, context)
        elapsed = time.monotonic() - started

        assert result.success is False
        assert "权限不足" in result.error
        # 权限拒绝发生在执行之前，不该等技能跑完
        assert elapsed < 0.4

    @pytest.mark.asyncio
    async def test_unknown_skill_is_reported(self):
        """未注册的技能给出明确错误。"""
        executor = _executor()
        result = await executor.execute_async("no_such_skill", {}, _context())
        assert result.success is False
        assert "未注册" in result.error
