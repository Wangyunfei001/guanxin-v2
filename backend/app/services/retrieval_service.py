"""检索服务模块。

负责从 ChromaDB 检索相关文档片段。
"""

from dataclasses import dataclass
from typing import List, Optional

from app.core.database import get_or_create_collection
from app.services.embedding_service import get_embedding_service


@dataclass
class RetrievalResult:
    """检索结果。"""

    chunk_id: str
    content: str
    score: float
    doc_id: str
    filename: str
    metadata: dict

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "score": round(self.score, 4),
            "doc_id": self.doc_id,
            "filename": self.filename,
            "metadata": self.metadata,
        }


class RetrievalService:
    """向量检索服务。"""

    def __init__(self) -> None:
        self.embedding_service = get_embedding_service()

    def retrieve(
        self,
        query: str,
        tenant_id: str,
        top_k: int = 5,
    ) -> List[RetrievalResult]:
        """检索与查询最相关的文档片段。

        Args:
            query: 查询文本
            tenant_id: 租户 ID
            top_k: 返回结果数量

        Returns:
            RetrievalResult 列表，按相关度降序排列
        """
        if not query.strip():
            return []

        # 生成查询向量
        query_embedding = self.embedding_service.embed_query(query)

        # 从 ChromaDB 检索
        collection = get_or_create_collection(tenant_id)
        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k, collection.count()) if collection.count() > 0 else top_k,
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            return []

        # 解析结果
        retrieval_results: List[RetrievalResult] = []

        if not results or not results.get("ids"):
            return retrieval_results

        ids = results["ids"][0] if results["ids"] else []
        documents = results["documents"][0] if results.get("documents") else []
        metadatas = results["metadatas"][0] if results.get("metadatas") else []
        distances = results["distances"][0] if results.get("distances") else []

        for i, chunk_id in enumerate(ids):
            content = documents[i] if i < len(documents) else ""
            metadata = metadatas[i] if i < len(metadatas) else {}
            distance = distances[i] if i < len(distances) else 1.0

            # ChromaDB 返回的是距离，转换为相似度分数 (0~1)
            score = max(0.0, 1.0 - distance / 2.0)

            retrieval_results.append(
                RetrievalResult(
                    chunk_id=chunk_id,
                    content=content,
                    score=score,
                    doc_id=metadata.get("doc_id", ""),
                    filename=metadata.get("filename", ""),
                    metadata=metadata,
                )
            )

        return retrieval_results


# 全局单例
_retrieval_service: Optional[RetrievalService] = None


def get_retrieval_service() -> RetrievalService:
    """获取全局检索服务单例。"""
    global _retrieval_service
    if _retrieval_service is None:
        _retrieval_service = RetrievalService()
    return _retrieval_service
