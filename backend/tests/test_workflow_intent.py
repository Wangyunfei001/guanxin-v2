"""写操作入口回归测试。

写操作只有一个入口：Agent 调 request_business_workflow。运行循环里
不再有正则旁路；问句也绝不产生变更类意图。
"""

import pytest

from app.workflows.intent import looks_like_question
from app.workflows.planner import detect_workflow_intent


class TestQuestionGuard:
    """问句识别。"""

    @pytest.mark.parametrize(
        "text",
        [
            "如何删除用户",
            "怎么删除用户？",
            "删除用户的流程是怎样的",
            "怎样创建一个用户",
            "删除用户需要什么权限",
            "请解释一下删除用户的流程",
            "介绍用户管理功能",
            "能删除用户吗",
            "用户是否可以删除",
        ],
    )
    def test_questions_are_detected(self, text):
        """问句被识别为问句。"""
        assert looks_like_question(text) is True

    def test_quoted_statement_is_not_a_question(self):
        """转述他人的话是陈述句，不是问句——交由模型判断，不靠正则。"""
        assert looks_like_question("他说要删除用户") is False

    @pytest.mark.parametrize(
        "text",
        [
            "创建一个用户",
            "删除用户 张三",
            "帮我删除用户李四",
            "更新用户 王五的邮箱",
            "新建一个账号",
            "导出数据",
            "批量删除用户",
        ],
    )
    def test_imperatives_are_not_questions(self, text):
        """祈使句不被误判为问句。"""
        assert looks_like_question(text) is False


class TestWorkflowIntentDetection:
    """意图检测不再把问句当成变更指令。"""

    @pytest.mark.parametrize(
        "text",
        [
            "如何删除用户",
            "怎么删除用户？",
            "解释一下删除用户的流程",
            "删除用户需要什么权限",
        ],
    )
    def test_question_never_yields_mutating_intent(self, text):
        """问句不产生任何变更类意图。"""
        assert detect_workflow_intent(text) == ""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("创建一个用户", "single_create"),
            ("帮我删除用户 张三", "single_delete"),
            ("更新用户 王五", "single_update"),
            ("导出数据", "batch_operation"),
        ],
    )
    def test_imperatives_still_yield_intent(self, text, expected):
        """明确的祈使请求仍然识别为变更意图。"""
        assert detect_workflow_intent(text) == expected

    def test_read_only_intent_is_not_a_workflow_intent(self):
        """只读意图不进入工作流。"""
        assert detect_workflow_intent("查询用户列表") == ""
        assert detect_workflow_intent("你好") == ""


class TestAgentPathHasNoBypass:
    """Agent 运行路径不再静默旁路模型。"""

    def test_question_creates_no_workflow(self, test_client, admin_headers, monkeypatch):
        """问句提交给 Agent 后不产生任何工作流记录。"""
        from langchain_core.messages import AIMessage

        from app.agent import deep_agent
        from app.services.workflow_store import get_workflow_store
        from tests.test_langchain import ScriptedModel, new_thread, settled, submit

        model = ScriptedModel(responses=[AIMessage(content="删除用户需要在管理页提交审批。")])
        monkeypatch.setattr(deep_agent, "_create_llm", lambda *a, **kw: model)

        cid = new_thread(test_client, admin_headers)
        submit(test_client, admin_headers, cid, "如何删除用户")
        state = settled(test_client, admin_headers, cid)

        assert state["run_status"] == "completed", state
        assert not state.get("workflow")
        assert get_workflow_store().get_active_for_conversation(
            cid, "tenant-a", "admin-001"
        ) is None

    def test_agent_answers_a_question_instead_of_asking_for_approval(
        self, test_client, admin_headers, monkeypatch
    ):
        """问句得到的是解释性回答，而不是审批卡。"""
        from langchain_core.messages import AIMessage

        from app.agent import deep_agent
        from tests.test_langchain import ScriptedModel, new_thread, settled, submit

        model = ScriptedModel(responses=[AIMessage(content="删除用户需要在管理页提交审批。")])
        monkeypatch.setattr(deep_agent, "_create_llm", lambda *a, **kw: model)

        cid = new_thread(test_client, admin_headers)
        submit(test_client, admin_headers, cid, "如何删除用户")
        state = settled(test_client, admin_headers, cid)

        replies = [m for m in state["messages"] if m["type"] == "ai"]
        assert replies
        assert "审批" in replies[-1]["content"]
        assert not state.get("workflow")
