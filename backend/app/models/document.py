"""文档模型模块。"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from typing import Any, Dict, List, Optional

from app.core.sqlite import connect, initialize_database, transaction


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
    """SQLite 文档存储管理器。"""

    def __init__(self) -> None:
        initialize_database()

    @staticmethod
    def _document_from_row(row: Any) -> Document:
        return Document(
            doc_id=row["doc_id"],
            tenant_id=row["tenant_id"],
            filename=row["filename"],
            file_path=row["file_path"],
            file_size=row["file_size"],
            file_type=row["file_type"],
            title=row["title"],
            status=DocumentStatus(row["status"]),
            chunk_count=row["chunk_count"],
            error_message=row["error_message"],
            metadata=json.loads(row["metadata_json"] or "{}"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _chunk_from_row(row: Any) -> DocumentChunk:
        return DocumentChunk(
            chunk_id=row["chunk_id"],
            doc_id=row["doc_id"],
            tenant_id=row["tenant_id"],
            content=row["content"],
            chunk_index=row["chunk_index"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )

    def add_document(self, doc: Document) -> None:
        """添加文档。"""
        with transaction() as conn:
            conn.execute(
                """
                INSERT INTO documents(
                    doc_id, tenant_id, filename, file_path, file_size, file_type,
                    title, status, chunk_count, error_message, metadata_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc.doc_id, doc.tenant_id, doc.filename, doc.file_path,
                    doc.file_size, doc.file_type, doc.title, doc.status.value,
                    doc.chunk_count, doc.error_message,
                    json.dumps(doc.metadata, ensure_ascii=False),
                    doc.created_at, doc.updated_at,
                ),
            )

    def get_document(self, doc_id: str) -> Optional[Document]:
        """获取文档。"""
        conn = connect()
        try:
            row = conn.execute(
                "SELECT * FROM documents WHERE doc_id = ?", (doc_id,)
            ).fetchone()
            return self._document_from_row(row) if row else None
        finally:
            conn.close()

    def update_document(self, doc_id: str, **kwargs: Any) -> Optional[Document]:
        """更新文档字段。"""
        doc = self.get_document(doc_id)
        if doc is None:
            return None
        for k, v in kwargs.items():
            if hasattr(doc, k):
                setattr(doc, k, v)
        doc.updated_at = datetime.now(timezone.utc).isoformat()
        with transaction() as conn:
            conn.execute(
                """
                UPDATE documents SET title=?, status=?, chunk_count=?,
                    error_message=?, metadata_json=?, updated_at=?
                WHERE doc_id=?
                """,
                (
                    doc.title,
                    doc.status.value if isinstance(doc.status, DocumentStatus) else doc.status,
                    doc.chunk_count,
                    doc.error_message,
                    json.dumps(doc.metadata, ensure_ascii=False),
                    doc.updated_at,
                    doc_id,
                ),
            )
        return doc

    def delete_document(self, doc_id: str) -> bool:
        """删除文档。"""
        with transaction() as conn:
            cursor = conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
            return cursor.rowcount > 0

    def list_documents(self, tenant_id: str) -> List[Document]:
        """列出租户的所有文档。"""
        conn = connect()
        try:
            rows = conn.execute(
                "SELECT * FROM documents WHERE tenant_id = ? ORDER BY created_at DESC",
                (tenant_id,),
            ).fetchall()
            return [self._document_from_row(row) for row in rows]
        finally:
            conn.close()

    def add_chunks(self, doc_id: str, chunks: List[DocumentChunk]) -> None:
        """添加文档分块。"""
        with transaction() as conn:
            conn.execute("DELETE FROM document_chunks WHERE doc_id = ?", (doc_id,))
            conn.executemany(
                """
                INSERT INTO document_chunks(
                    chunk_id, doc_id, tenant_id, content, chunk_index, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        chunk.chunk_id,
                        chunk.doc_id,
                        chunk.tenant_id,
                        chunk.content,
                        chunk.chunk_index,
                        json.dumps(chunk.metadata, ensure_ascii=False),
                    )
                    for chunk in chunks
                ],
            )

    def get_chunks(self, doc_id: str) -> List[DocumentChunk]:
        """获取文档分块。"""
        conn = connect()
        try:
            rows = conn.execute(
                "SELECT * FROM document_chunks WHERE doc_id = ? ORDER BY chunk_index",
                (doc_id,),
            ).fetchall()
            return [self._chunk_from_row(row) for row in rows]
        finally:
            conn.close()


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
