"""文档分块模块。

支持按固定大小 + 重叠窗口进行文本分块，
也支持按段落分块。
"""

from dataclasses import dataclass
from typing import List

from app.models.document import DocumentChunk


@dataclass
class ChunkConfig:
    """分块配置。"""

    chunk_size: int = 500
    chunk_overlap: int = 50
    separator: str = "\n\n"


def chunk_text(
    text: str,
    doc_id: str,
    tenant_id: str,
    config: ChunkConfig | None = None,
) -> List[DocumentChunk]:
    """将文本分块。

    Args:
        text: 待分块的文本
        doc_id: 文档 ID
        tenant_id: 租户 ID
        config: 分块配置，为空则使用默认配置

    Returns:
        DocumentChunk 列表
    """
    if config is None:
        config = ChunkConfig()

    if not text.strip():
        return []

    # 先按段落分割
    paragraphs = _split_paragraphs(text, config.separator)

    # 再按 chunk_size 组合段落
    chunks_text: List[str] = []
    current_chunk = ""
    for para in paragraphs:
        if len(current_chunk) + len(para) > config.chunk_size and current_chunk:
            chunks_text.append(current_chunk.strip())
            # 保留重叠部分
            overlap = current_chunk[-config.chunk_overlap :] if config.chunk_overlap > 0 else ""
            current_chunk = overlap + para
        else:
            current_chunk = current_chunk + config.separator + para if current_chunk else para

    if current_chunk.strip():
        chunks_text.append(current_chunk.strip())

    # 如果单段落超过 chunk_size，进行硬切分
    final_chunks: List[str] = []
    for chunk in chunks_text:
        if len(chunk) > config.chunk_size * 2:
            for i in range(0, len(chunk), config.chunk_size):
                final_chunks.append(chunk[i : i + config.chunk_size])
        else:
            final_chunks.append(chunk)

    # 生成 DocumentChunk 对象
    import uuid

    chunks: List[DocumentChunk] = []
    for idx, content in enumerate(final_chunks):
        if not content.strip():
            continue
        chunk = DocumentChunk(
            chunk_id=str(uuid.uuid4()),
            doc_id=doc_id,
            tenant_id=tenant_id,
            content=content,
            chunk_index=idx,
            metadata={
                "chunk_size": len(content),
                "doc_id": doc_id,
            },
        )
        chunks.append(chunk)

    return chunks


def _split_paragraphs(text: str, separator: str) -> List[str]:
    """按分隔符分割段落。"""
    if not text:
        return []
    parts = text.split(separator)
    return [p.strip() for p in parts if p.strip()]
