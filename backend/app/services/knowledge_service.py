"""知识库服务模块。

负责文档上传、解析、分块、embedding、存储的完整流程。
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from app.core.database import get_or_create_collection
from app.core.tenant import get_tenant_id
from app.models.document import Document, DocumentStatus, DocumentStore, get_document_store
from app.services.chunker import ChunkConfig, chunk_text
from app.services.document_parser import detect_file_type, parse_file
from app.services.embedding_service import get_embedding_service

logger = logging.getLogger(__name__)


class KnowledgeService:
    """知识库管理服务。"""

    def __init__(self) -> None:
        self.embedding_service = get_embedding_service()
        self.store: DocumentStore = get_document_store()

    async def upload_document(
        self,
        tenant_id: str,
        filename: str,
        content: bytes,
        title: str = "",
    ) -> Document:
        """上传并处理文档。

        整个同步阻塞流程（文件写入、PDF 解析、分块、Embedding HTTP 调用、
        ChromaDB 写入）通过 ``asyncio.to_thread`` 放到工作线程执行，避免阻塞
        事件循环（P0-1）。

        Args:
            tenant_id: 租户 ID
            filename: 文件名
            content: 文件内容字节
            title: 文档标题

        Returns:
            创建的 Document 对象
        """
        # P0-1: 将核心同步阻塞逻辑交给线程池，保持 async 签名不变
        return await asyncio.to_thread(
            self._process_document,
            tenant_id,
            filename,
            content,
            title,
        )

    def _process_document(
        self,
        tenant_id: str,
        filename: str,
        content: bytes,
        title: str = "",
    ) -> Document:
        """文档处理的同步核心逻辑（在线程池中执行）。

        Args:
            tenant_id: 租户 ID
            filename: 文件名
            content: 文件内容字节
            title: 文档标题

        Returns:
            创建的 Document 对象
        """
        file_type = detect_file_type(filename)
        doc_id = str(uuid.uuid4())

        # 保存文件到磁盘
        from app.config import settings

        file_path = settings.upload_path / f"{doc_id}_{filename}"
        file_path.write_bytes(content)

        # 创建文档记录
        doc = Document(
            doc_id=doc_id,
            tenant_id=tenant_id,
            filename=filename,
            file_path=str(file_path),
            file_size=len(content),
            file_type=file_type,
            title=title or filename,
            status=DocumentStatus.PARSING,
        )
        self.store.add_document(doc)

        # 解析文档
        text = parse_file(str(file_path), file_type)
        if not text:
            self.store.update_document(
                doc_id,
                status=DocumentStatus.FAILED,
                error_message="文档解析失败：无法提取文本内容",
            )
            return doc

        # 分块
        self.store.update_document(doc_id, status=DocumentStatus.CHUNKING)
        chunks = chunk_text(text, doc_id, tenant_id)
        self.store.add_chunks(doc_id, chunks)

        # 生成 embedding 并存储到 ChromaDB
        self.store.update_document(doc_id, status=DocumentStatus.EMBEDDING)
        if chunks:
            texts = [c.content for c in chunks]
            try:
                # P0-3: 显式获取是否回退到本地伪随机向量，用于元数据标注
                embeddings, is_fallback = (
                    self.embedding_service.embed_texts_with_fallback(texts)
                )

                collection = get_or_create_collection(tenant_id)
                collection.add(
                    ids=[c.chunk_id for c in chunks],
                    embeddings=embeddings,
                    documents=texts,
                    metadatas=[
                        {
                            "doc_id": doc_id,
                            "tenant_id": tenant_id,
                            "filename": filename,
                            "chunk_index": c.chunk_index,
                            # 标注该 chunk 是否使用回退向量，便于检索时识别
                            "fallback": is_fallback,
                        }
                        for c in chunks
                    ],
                )

                # 成功：标记为 READY
                self.store.update_document(
                    doc_id,
                    status=DocumentStatus.READY,
                    chunk_count=len(chunks),
                )
            except Exception as e:
                # P0-2: 异常路径必须更新状态，避免卡死在 EMBEDDING
                logger.error("文档 %s Embedding/向量存储失败: %s", doc_id, e)
                self.store.update_document(
                    doc_id,
                    status=DocumentStatus.FAILED,
                    error_message=f"Embedding 或向量存储失败: {e}",
                )
        else:
            # 无分块也视为处理完成
            self.store.update_document(
                doc_id,
                status=DocumentStatus.READY,
                chunk_count=0,
            )

        return doc

    def list_documents(self, tenant_id: str) -> List[Document]:
        """列出租户的所有文档。"""
        return self.store.list_documents(tenant_id)

    def get_document(self, doc_id: str, tenant_id: str) -> Optional[Document]:
        """获取文档详情。"""
        doc = self.store.get_document(doc_id)
        if doc and doc.tenant_id == tenant_id:
            return doc
        return None

    def delete_document(self, doc_id: str, tenant_id: str) -> bool:
        """删除文档及其向量数据。"""
        doc = self.store.get_document(doc_id)
        if not doc or doc.tenant_id != tenant_id:
            return False

        # 从 ChromaDB 删除向量
        chunks = self.store.get_chunks(doc_id)
        if chunks:
            collection = get_or_create_collection(tenant_id)
            try:
                collection.delete(ids=[c.chunk_id for c in chunks])
            except Exception:
                pass

        # 删除文件
        from pathlib import Path

        try:
            Path(doc.file_path).unlink(missing_ok=True)
        except Exception:
            pass

        # 删除文档记录
        self.store.delete_document(doc_id)
        return True


# 全局单例
_knowledge_service: Optional[KnowledgeService] = None


def get_knowledge_service() -> KnowledgeService:
    """获取全局知识库服务单例。"""
    global _knowledge_service
    if _knowledge_service is None:
        _knowledge_service = KnowledgeService()
    return _knowledge_service
