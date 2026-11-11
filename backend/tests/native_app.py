"""Browser test entrypoint: real Deep Agents, deterministic streaming model.

Never imported by app.main or a production launch. No external model requests.
"""
import asyncio
import time

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk, ChatResult

from app.config import settings

if settings.app_env != "test":
    raise RuntimeError("The native browser fixture is restricted to APP_ENV=test")


class BrowserModel(BaseChatModel):
    @property
    def _llm_type(self):
        return "guanxin-browser-test"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        raise AssertionError("Browser fixture requires streaming")

    def _chunks(self, messages):
        text = next((m.content for m in reversed(messages) if m.type == "human"), "")
        last_is_tool = messages[-1].type == "tool"
        if not last_is_tool:
            # The business-mutation path goes through the real agent tool, so the
            # browser test covers agent -> tool -> approval instead of a shortcut.
            if "创建一个用户" in text:
                yield AIMessageChunk(content="", tool_call_chunks=[{
                    "name": "request_business_workflow",
                    "args": '{"goal":"创建一个用户"}',
                    "id": "browser-workflow", "index": 0}])
                return
            if "生成测试报告" in text:
                yield AIMessageChunk(content="", tool_call_chunks=[{
                    "name": "write_file", "args": '{"file_path":"/reports/browser.md","content":"# 测试报告\\n这是端到端测试产物。"}',
                    "id": "browser-write", "index": 0}])
                return
        answer = "测试报告已保存到 /reports/browser.md。" if "生成测试报告" in text else "这是一段用于验证原生流式接入的测试回复。"
        for word in answer:
            yield AIMessageChunk(content=word)

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        for chunk in self._chunks(messages):
            time.sleep(.03)
            yield ChatGenerationChunk(message=chunk)

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        for chunk in self._chunks(messages):
            await asyncio.sleep(.03)
            yield ChatGenerationChunk(message=chunk)


from app.agent import deep_agent
from app.main import create_app

deep_agent.create_llm = lambda *a, **kw: BrowserModel()
app = create_app()
