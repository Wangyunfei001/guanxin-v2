"""Shared configured LangChain model factory."""
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

# 占位符密钥——视为未配置。
PLACEHOLDER_API_KEY = "sk-your-api-key-here"


class LLMConfigurationError(RuntimeError):
    """模型可用但初始化失败（地址错误、模型名无效、依赖缺失等）。"""


def create_llm(model_name: str, temperature: float, max_tokens: int = 4096):
    """创建 LLM 实例。

    Args:
        model_name: 模型名称
        temperature: 温度
        max_tokens: 最大输出 token

    Returns:
        ChatOpenAI 实例；**未配置密钥**时返回 None，其他初始化失败抛出
        :class:`LLMConfigurationError`。

    之前这里把任何异常都吞成 None，上层一律报「请先配置 OPENAI_API_KEY」——
    401、地址写错、模型名无效全被误诊成同一个问题，且没有任何日志。
    """
    api_key = settings.openai_api_key
    if not api_key or api_key == PLACEHOLDER_API_KEY:
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
            stream_usage=True,
            max_tokens=max_tokens,
            **model_kwargs,
        )
    except Exception as exc:
        logger.exception("模型初始化失败: model=%s base_url=%s", model_name, settings.openai_api_base)
        raise LLMConfigurationError(f"模型 {model_name} 初始化失败: {exc}") from exc
