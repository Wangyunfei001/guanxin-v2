"""Embedding 服务模块。

支持 OpenAI Embedding API 和本地回退（随机向量）。
"""

import hashlib
import logging
import random
from typing import List, Optional, Tuple

from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Embedding 服务。"""

    def __init__(self) -> None:
        self._model: str = settings.embedding_model
        self._api_key: str = settings.embedding_api_key or settings.openai_api_key
        self._api_base: str = settings.embedding_api_base
        self._client = None
        # 根据 model 自适应维度
        if "text-embedding-v3" in self._model:
            self._dimension: int = 1024
        elif "text-embedding-ada-002" in self._model:
            self._dimension: int = 1536
        else:
            self._dimension: int = 1536

    def _get_client(self):
        """延迟初始化 OpenAI 客户端。"""
        if self._client is not None:
            return self._client

        if self._api_key and self._api_key != "sk-your-api-key-here":
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
