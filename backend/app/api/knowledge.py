"""知识库 API 模块。

提供文档上传、列表、删除、检索等接口。
"""

import asyncio

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.config import settings
from app.core.deps import get_current_user
from app.core.responses import success
from app.core.tenant import get_tenant_id
from app.models.tenant import User
from app.services.knowledge_service import get_knowledge_service
from app.services.retrieval_service import get_retrieval_service

router = APIRouter(prefix="/knowledge", tags=["知识库"])

# 上传读取的分块大小（1 MiB）
UPLOAD_CHUNK_SIZE = 1 << 20


def _upload_limit_bytes() -> int:
    """单次上传允许的最大字节数。"""
    return settings.max_upload_size_mb * 1024 * 1024


async def _read_limited(file: UploadFile, limit: int) -> bytes:
    """分块读取上传内容，超过上限立即中断。

    不把整个文件一次性读进内存，避免超限请求耗尽 worker 内存。
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(UPLOAD_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(
                status_code=413,
                detail=f"文件超过 {settings.max_upload_size_mb} MB 上限",
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(""),
    user: User = Depends(get_current_user),
):
    """上传文档到知识库。"""
    tenant_id = get_tenant_id() or user.tenant_id
    limit = _upload_limit_bytes()

    # 预检：解析器已知长度时直接拒绝，不必先读进内存。
    if file.size is not None and file.size > limit:
        raise HTTPException(
            status_code=413,
            detail=f"文件超过 {settings.max_upload_size_mb} MB 上限",
        )

    content = await _read_limited(file, limit)
    service = get_knowledge_service()
    doc = await service.upload_document(
        tenant_id=tenant_id,
        filename=file.filename or "unknown.txt",
        content=content,
        title=title,
    )
    return success(doc.to_dict())


@router.get("/documents")
async def list_documents(user: User = Depends(get_current_user)):
    """列出知识库文档。"""
    tenant_id = get_tenant_id() or user.tenant_id
    service = get_knowledge_service()
    docs = service.list_documents(tenant_id)
    return success([d.to_dict() for d in docs])


@router.get("/documents/{doc_id}")
async def get_document(doc_id: str, user: User = Depends(get_current_user)):
    """获取文档详情。"""
    tenant_id = get_tenant_id() or user.tenant_id
    service = get_knowledge_service()
    doc = service.get_document(doc_id, tenant_id)
    if doc is None:
        return {"code": 4041, "message": "文档未找到", "data": None}
    payload = doc.to_dict()
    payload["chunks"] = [
        chunk.to_dict() for chunk in service.store.get_chunks(doc_id)
    ]
    return success(payload)


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, user: User = Depends(get_current_user)):
    """删除文档。"""
    tenant_id = get_tenant_id() or user.tenant_id
    service = get_knowledge_service()
    deleted = service.delete_document(doc_id, tenant_id)
    if not deleted:
        return {"code": 4041, "message": "文档未找到", "data": None}
    return success({"deleted": True})


class RetrieveRequest(BaseModel):
    """检索请求模型。"""

    query: str
    top_k: int = 5


@router.post("/retrieve")
async def retrieve(
    request: RetrieveRequest,
    user: User = Depends(get_current_user),
):
    """检索知识库。"""
    tenant_id = get_tenant_id() or user.tenant_id
    service = get_retrieval_service()
    # P0-1: service.retrieve 是同步阻塞方法（含 Embedding 调用与
    # ChromaDB query），放到线程池执行，避免阻塞事件循环。
    results = await asyncio.to_thread(
        service.retrieve,
        query=request.query,
        tenant_id=tenant_id,
        top_k=request.top_k,
    )
    return success([r.to_dict() for r in results])
