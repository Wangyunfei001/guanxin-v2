"""Embedding 服务模块。

支持 OpenAI 兼容 API、Ollama 本地语义模型和显式本地回退。
"""

import hashlib
import logging
import random
from typing import List, Optional, Tuple

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingProviderError(RuntimeError):
    """Embedding provider 返回无效数据或无法访问。"""


class EmbeddingService:
    """Embedding 服务。"""

    def __init__(self) -> None:
        self._provider: str = settings.embedding_provider
        self._model: str = settings.embedding_model
        self._api_key: str = (
            settings.embedding_api_key if self._provider == "openai" else ""
        )
        self._api_base: str = settings.embedding_api_base
        self._ollama_base_url: str = settings.ollama_base_url.rstrip("/")
        self._client = None
        self._dimension: int = settings.embedding_dimension

    @property
    def provider(self) -> str:
        return self._provider

    def _get_client(self):
        """延迟初始化 OpenAI 兼容客户端。"""
        if self._client is not None:
            return self._client

        if (
            self._provider == "openai"
            and self._api_key
            and self._api_key != "sk-your-api-key-here"
        ):
            try:
                from openai import OpenAI

                self._client = OpenAI(
                    api_key=self._api_key,
                    base_url=self._api_base,
                )
            except ImportError:
                self._client = None
        return self._client

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """生成文本的 embedding 向量。

        Args:
            texts: 文本列表

        Returns:
            向量列表，每个向量是 float 列表
        """
        embeddings, _ = self.embed_texts_with_fallback(texts)
        return embeddings

    def embed_texts_with_fallback(
        self, texts: List[str]
    ) -> Tuple[List[List[float]], bool]:
        """生成文本的 embedding 向量，并返回是否回退到本地伪随机向量。

        Args:
            texts: 文本列表

        Returns:
            二元组 (embeddings, is_fallback)，其中 is_fallback 为 True 表示
            由于 Embedding API 不可用而使用了本地伪随机向量。
        """
        if not texts:
            return [], False

        if self._provider == "ollama":
            return self._embed_with_ollama(texts), False

        if self._provider == "local":
            return [self._local_embed(text) for text in texts], True

        client = self._get_client()
        if client is not None:
            try:
                response = client.embeddings.create(
                    input=texts,
                    model=self._model,
                )
                return [item.embedding for item in response.data], False
            except Exception as e:
                # 不再静默回退：记录明确告警，便于 Demo/排查时感知
                logger.warning(
                    "Embedding API 调用失败，回退到本地伪随机向量: %s", e
                )

        # 本地回退：使用确定性伪随机向量
        return [self._local_embed(text) for text in texts], True

    def _embed_with_ollama(self, texts: List[str]) -> List[List[float]]:
        """通过 Ollama 原生批量接口生成语义向量。"""
        try:
            response = httpx.post(
                f"{self._ollama_base_url}/api/embed",
                json={"model": self._model, "input": texts},
                timeout=120.0,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise EmbeddingProviderError(
                f"Ollama Embedding 调用失败: {type(exc).__name__}"
            ) from exc

        vectors = payload.get("embeddings") if isinstance(payload, dict) else None
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            raise EmbeddingProviderError(
                "Ollama Embedding 返回数量与输入数量不一致"
            )

        normalized: List[List[float]] = []
        for vector in vectors:
            if not isinstance(vector, list) or len(vector) != self._dimension:
                actual = len(vector) if isinstance(vector, list) else "invalid"
                raise EmbeddingProviderError(
                    "Ollama Embedding 维度错误: "
                    f"期望 {self._dimension}，实际 {actual}"
                )
            if not all(
                isinstance(value, (int, float)) and not isinstance(value, bool)
                for value in vector
            ):
                raise EmbeddingProviderError("Ollama Embedding 包含非数值元素")
            normalized.append([float(value) for value in vector])
        return normalized

    def embed_query(self, text: str) -> List[float]:
        """生成查询文本的 embedding 向量。"""
        results = self.embed_texts([text])
        return results[0] if results else self._local_embed(text)

    def check_connectivity(self) -> bool:
        """检查 Embedding API 是否可用（连通性探针）。

        在应用启动时调用，用于提前发现 API Key 失效 / 网络不可达等问题。
        不会抛出异常，仅在不可用时返回 False 并输出告警。

        Returns:
            True 表示 Embedding API 可用，False 表示不可用。
        """
        if self._provider == "local":
            return True

        if self._provider == "ollama":
            try:
                self._embed_with_ollama(["__connectivity_check__"])
                return True
            except EmbeddingProviderError as exc:
                logger.warning("Ollama Embedding 连通性检查失败: %s", exc)
                return False

        client = self._get_client()
        if client is None:
            logger.warning(
                "Embedding API 未配置（缺少 API Key），将回退到本地伪随机向量。"
            )
            return False
        try:
            client.embeddings.create(
                input=["__connectivity_check__"],
                model=self._model,
            )
            return True
        except Exception as e:
            logger.warning("Embedding API 连通性检查失败: %s", e)
            return False

    def _local_embed(self, text: str) -> List[float]:
        """本地确定性伪随机 embedding（回退方案）。

        使用文本哈希作为随机种子，生成固定维度的向量。
        """
        seed = int(hashlib.md5(text.encode()).hexdigest(), 16) % (2**32)
        rng = random.Random(seed)
        # 生成单位向量
        vec = [rng.gauss(0, 1) for _ in range(self._dimension)]
        magnitude = sum(x * x for x in vec) ** 0.5
        if magnitude > 0:
            vec = [x / magnitude for x in vec]
        return vec


# 全局单例
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """获取全局 Embedding 服务单例。"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
