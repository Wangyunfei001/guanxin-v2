"""Shared configured LangChain model factory."""
from typing import Any
from app.config import settings


def _create_llm(model_name: str, temperature: float, max_tokens: int = 4096):
    """创建 LLM 实例。

    Args:
        model_name: 模型名称
        temperature: 温度

    Returns:
        ChatOpenAI 实例，失败返回 None
    """
    api_key = settings.openai_api_key
    if not api_key or api_key == "sk-your-api-key-here":
        return None

    try:
        from langchain_openai import ChatOpenAI

        model_kwargs: dict[str, Any] = {}
        # DeepSeek V4 enables thinking by default. This app deliberately keeps
        # Chat Completions non-thinking so forced tool choice and LangChain's
        # structured-output calls remain compatible, and no raw CoT needs to be
        # replayed across tool turns. Research uses the Responses API separately.
        if model_name.startswith("deepseek-v4-"):
            model_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=api_key,
            base_url=settings.openai_api_base,
            streaming=True,
            max_tokens=max_tokens,
            **model_kwargs,
        )
    except Exception:
        return None


def get_tools_desc() -> str:
    """获取工具描述文本。"""
    return get_tools_description(get_tools())
