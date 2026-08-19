"""数据库模块：ChromaDB 客户端管理。"""

import threading
from typing import Optional

import chromadb

from app.config import settings

# 全局 ChromaDB 客户端单例
_chroma_client: Optional[chromadb.PersistentClient] = None
_chroma_lock = threading.Lock()


def get_chroma_client() -> chromadb.PersistentClient:
    """获取 ChromaDB 持久化客户端单例。

    Returns:
        chromadb.PersistentClient 实例
    """
    global _chroma_client
    if _chroma_client is None:
        with _chroma_lock:
            if _chroma_client is None:
                _chroma_client = chromadb.PersistentClient(
                    path=str(settings.chroma_path),
                )
    return _chroma_client


def get_or_create_collection(tenant_id: str):
    """获取或创建租户的知识库集合。

    Args:
        tenant_id: 租户 ID

    Returns:
        ChromaDB Collection 对象
    """
    client = get_chroma_client()
    collection_name = f"tenant-{tenant_id}-kb"
    return client.get_or_create_collection(
        name=collection_name,
        metadata={"tenant_id": tenant_id, "description": "知识库向量存储"},
    )


def delete_collection(tenant_id: str) -> None:
    """删除租户的知识库集合。

    Args:
        tenant_id: 租户 ID
    """
    client = get_chroma_client()
    collection_name = f"tenant-{tenant_id}-kb"
    try:
        client.delete_collection(name=collection_name)
    except Exception:
        pass  # 集合不存在时忽略


def list_collections() -> list:
    """列出所有集合名称。"""
    client = get_chroma_client()
    return [c.name for c in client.list_collections()]
