"""文档模型模块。"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class DocumentStatus(str, Enum):
    """文档处理状态。"""

    PENDING = "pending"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    READY = "ready"
    FAILED = "failed"


@dataclass
class Document:
    """文档模型。"""

    doc_id: str
    tenant_id: str
    filename: str
    file_path: str
    file_size: int
    file_type: str
    title: str = ""
    status: DocumentStatus = DocumentStatus.PENDING
    chunk_count: int = 0
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "doc_id": self.doc_id,
            "tenant_id": self.tenant_id,
            "filename": self.filename,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "title": self.title or self.filename,
            "status": self.status.value,
            "chunk_count": self.chunk_count,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class DocumentChunk:
    """文档分块模型。"""

    chunk_id: str
    doc_id: str
    tenant_id: str
    content: str
    chunk_index: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "content": self.content[:200] + "..." if len(self.content) > 200 else self.content,
            "chunk_index": self.chunk_index,
            "metadata": self.metadata,
        }


class DocumentStore:
    """文档存储管理器：内存存储。"""

    def __init__(self) -> None:
        self._documents: Dict[str, Document] = {}  # key: doc_id
        self._chunks: Dict[str, List[DocumentChunk]] = {}  # key: doc_id

    def add_document(self, doc: Document) -> None:
        """添加文档。"""
        self._documents[doc.doc_id] = doc

    def get_document(self, doc_id: str) -> Optional[Document]:
        """获取文档。"""
        return self._documents.get(doc_id)

    def update_document(self, doc_id: str, **kwargs: Any) -> Optional[Document]:
        """更新文档字段。"""
        doc = self._documents.get(doc_id)
        if doc is None:
            return None
        for k, v in kwargs.items():
            if hasattr(doc, k):
                setattr(doc, k, v)
        doc.updated_at = datetime.now(timezone.utc).isoformat()
        return doc

    def delete_document(self, doc_id: str) -> bool:
        """删除文档。"""
        if doc_id in self._documents:
            del self._documents[doc_id]
            self._chunks.pop(doc_id, None)
            return True
        return False

    def list_documents(self, tenant_id: str) -> List[Document]:
        """列出租户的所有文档。"""
        return [d for d in self._documents.values() if d.tenant_id == tenant_id]

    def add_chunks(self, doc_id: str, chunks: List[DocumentChunk]) -> None:
        """添加文档分块。"""
        self._chunks[doc_id] = chunks

    def get_chunks(self, doc_id: str) -> List[DocumentChunk]:
        """获取文档分块。"""
        return self._chunks.get(doc_id, [])


# 全局文档存储单例
_document_store: Optional[DocumentStore] = None


def get_document_store() -> DocumentStore:
    """获取全局文档存储单例。"""
    global _document_store
    if _document_store is None:
        _document_store = DocumentStore()
    return _document_store


def reset_document_store() -> None:
    """重置文档存储（用于测试）。"""
    global _document_store
    _document_store = None
