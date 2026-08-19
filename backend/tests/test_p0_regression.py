"""P0 回归测试套件。

针对后端 ChromaDB 的三个 P0 问题进行回归验证：

- P0-1 事件循环阻塞：``upload_document`` 的同步阻塞逻辑应通过
  ``asyncio.to_thread`` 卸载到工作线程；``/retrieve`` 路由同理。
- P0-2 上传异常状态卡死：embedding / ChromaDB 写入失败时，文档状态必须
  更新为 ``FAILED`` 且 ``error_message`` 非空；正常路径为 ``READY``；
  空 chunks 也显式标记为 ``READY``。
- P0-3 Embedding 静默回退随机向量：``embed_texts_with_fallback`` 在 API
  失败时返回 ``(vectors, True)`` 并记录 warning；正常返回 ``(vectors, False)``；
  ``check_connectivity()`` 在 API 不可达时返回 ``False`` 且不抛异常；
  ``main.py`` lifespan 中调用 ``check_connectivity()`` 且失败时不影响启动。
"""

import asyncio
import inspect
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.document import DocumentStatus, reset_document_store
from app.services.embedding_service import EmbeddingService


@pytest.fixture(autouse=True)
def _reset_store():
    """每个测试前重置内存文档存储，避免状态串扰。"""
    reset_document_store()
    yield


# =========================================================================
# P0-1：事件循环阻塞
# =========================================================================
class TestP0_1_AsyncNonBlocking:
    """验证上传 / 检索的同步阻塞逻辑被卸载到线程池。"""

    def test_upload_document_is_async_and_offloads_to_thread(self):
        """upload_document 必须是真正的 async，并通过 to_thread 调用
        ``_process_document``（同步私有方法）。"""
        from app.services.knowledge_service import KnowledgeService

        # 结构校验：upload_document 是协程函数，_process_document 不是
        assert inspect.iscoroutinefunction(KnowledgeService.upload_document)
        assert not inspect.iscoroutinefunction(KnowledgeService._process_document)

        service = KnowledgeService()
        # 用 mock 替换外部依赖，使 _process_document 能跑完
        service.embedding_service = MagicMock()
        service.embedding_service.embed_texts_with_fallback.side_effect = (
            lambda texts: ([[0.1] * 8 for _ in texts], False)
        )

        captured = {}

        async def fake_to_thread(func, *args, **kwargs):
            captured["func"] = func
            captured["args"] = args
            return func(*args, **kwargs)

        with patch(
            "app.services.knowledge_service.asyncio.to_thread", fake_to_thread
        ), patch(
            "app.services.knowledge_service.get_or_create_collection",
            return_value=MagicMock(),
        ):
            doc = asyncio.run(
                service.upload_document(
                    tenant_id="t1",
                    filename="a.txt",
                    content=("这是一段用于测试的内容。" * 5).encode("utf-8"),
                    title="t",
                )
            )

        # 验证 to_thread 确实把同步核心方法卸载出去了
        # 注意：实例方法每次访问都会生成新的 bound method 对象，
        # 因此比较底层 __func__ 而非身份。
        assert captured["func"].__func__ is KnowledgeService._process_document
        assert captured["func"].__self__ is service
        assert captured["args"][0] == "t1"
        assert captured["args"][1] == "a.txt"
        assert isinstance(doc, object)

    def test_retrieve_route_offloads_to_thread(self, test_client, admin_headers):
        """/retrieve 路由应通过 asyncio.to_thread 把同步检索放到工作线程，
        不阻塞事件循环。"""

        class FakeRetrievalService:
            def __init__(self):
                self.captured_loop = "unset"

            def retrieve(self, query, tenant_id, top_k=5):
                # 若运行在事件循环所在线程，这里能取到 loop；
                # 卸载到线程池时应取不到（返回 None）。
                try:
                    self.captured_loop = asyncio.get_running_loop()
                except RuntimeError:
                    self.captured_loop = None
                return []

        fake = FakeRetrievalService()
        with patch(
            "app.api.knowledge.get_retrieval_service", return_value=fake
        ):
            response = test_client.post(
                "/api/knowledge/retrieve",
                headers=admin_headers,
                json={"query": "测试查询", "top_k": 3},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        # 关键断言：同步 retrieve 运行在 worker 线程（无事件循环），
        # 证明事件循环未被阻塞。
        assert fake.captured_loop is None


# =========================================================================
# P0-2：上传异常状态卡死
# =========================================================================
class TestP0_2_ExceptionStatus:
    """验证 embedding / 向量写入失败不会让文档卡在 EMBEDDING。"""

    @staticmethod
    def _build_service(embed_side_effect, collection_mock):
        from app.services.knowledge_service import KnowledgeService

        service = KnowledgeService()
        service.embedding_service = MagicMock()
        service.embedding_service.embed_texts_with_fallback.side_effect = (
            embed_side_effect
        )
        return service, collection_mock

    def test_upload_failure_marks_failed_with_error(self):
        """embedding 抛异常时，文档状态应为 FAILED 且 error_message 非空。"""
        from app.services.knowledge_service import KnowledgeService, get_document_store

        service = KnowledgeService()
        service.embedding_service = MagicMock()
        service.embedding_service.embed_texts_with_fallback.side_effect = RuntimeError(
            "embedding boom"
        )

        with patch(
            "app.services.knowledge_service.get_or_create_collection",
            return_value=MagicMock(),
        ):
            doc = asyncio.run(
                service.upload_document(
                    tenant_id="t2",
                    filename="b.txt",
                    content=("会失败的内容用于测试异常路径。" * 5).encode("utf-8"),
                )
            )

        stored = get_document_store().get_document(doc.doc_id)
        assert stored is not None
        assert stored.status == DocumentStatus.FAILED
        assert stored.error_message
        assert "embedding boom" in stored.error_message.lower() or "embedding" in stored.error_message.lower()

    def test_upload_success_marks_ready(self):
        """正常 embedding + 写入时，文档状态应为 READY 且 chunk_count > 0。"""
        from app.services.knowledge_service import KnowledgeService, get_document_store

        service = KnowledgeService()
        service.embedding_service = MagicMock()
        service.embedding_service.embed_texts_with_fallback.side_effect = (
            lambda texts: ([[0.2] * 8 for _ in texts], False)
        )

        collection = MagicMock()
        with patch(
            "app.services.knowledge_service.get_or_create_collection",
            return_value=collection,
        ):
            doc = asyncio.run(
                service.upload_document(
                    tenant_id="t3",
                    filename="c.txt",
                    content=("正常流程的内容用于验证就绪状态。" * 10).encode("utf-8"),
                )
            )

        stored = get_document_store().get_document(doc.doc_id)
        assert stored.status == DocumentStatus.READY
        assert stored.chunk_count and stored.chunk_count > 0
        assert collection.add.called

    def test_empty_chunks_marks_ready(self):
        """当分块为空时，文档应显式标记为 READY（chunk_count=0）。"""
        from app.services.knowledge_service import KnowledgeService, get_document_store

        service = KnowledgeService()
        service.embedding_service = MagicMock()

        # 让 chunk_text 返回空列表，触发空 chunks 分支
        with patch(
            "app.services.knowledge_service.chunk_text", return_value=[]
        ), patch(
            "app.services.knowledge_service.get_or_create_collection",
            return_value=MagicMock(),
        ):
            doc = asyncio.run(
                service.upload_document(
                    tenant_id="t4",
                    filename="d.txt",
                    content="内容会被分块成空（测试中 mock 掉）。".encode("utf-8"),
                )
            )

        stored = get_document_store().get_document(doc.doc_id)
        assert stored.status == DocumentStatus.READY
        assert stored.chunk_count == 0

    def test_fallback_metadata_annotation(self):
        """embedding 回退时，写入 ChromaDB 的每个 chunk metadata 必须包含
        ``fallback: True`` 标注（P0-3 与 knowledge_service 的联动）。"""
        from app.services.knowledge_service import KnowledgeService, get_document_store

        service = KnowledgeService()
        service.embedding_service = MagicMock()
        # 模拟 embedding 失败 -> 回退（is_fallback=True）
        service.embedding_service.embed_texts_with_fallback.side_effect = (
            lambda texts: ([[0.3] * 8 for _ in texts], True)
        )

        collected = {}

        def fake_add(ids, embeddings, documents, metadatas):
            collected["metadatas"] = metadatas

        collection = MagicMock()
        collection.add.side_effect = fake_add

        with patch(
            "app.services.knowledge_service.get_or_create_collection",
            return_value=collection,
        ):
            asyncio.run(
                service.upload_document(
                    tenant_id="t5",
                    filename="e.txt",
                    content=("用于验证回退元数据的测试内容。" * 6).encode("utf-8"),
                )
            )

        assert collected.get("metadatas"), "collection.add 未被调用"
        for meta in collected["metadatas"]:
            assert meta.get("fallback") is True


# =========================================================================
# P0-3：Embedding 静默回退随机向量
# =========================================================================
class TestP0_3_EmbeddingFallback:
    """验证 embed_texts_with_fallback / check_connectivity 的回退与告警。"""

    def test_fallback_true_and_warns_on_api_exception(self, caplog):
        """API Client 存在但调用抛异常时，应回退本地随机向量并返回
        ``(vectors, True)``，且记录 warning（P0-3 不再静默回退）。"""
        boom = RuntimeError("api down")
        fake_client = SimpleNamespace(
            embeddings=SimpleNamespace(create=MagicMock(side_effect=boom))
        )
        service = EmbeddingService()
        service._get_client = lambda: fake_client  # 客户端存在但调用失败

        with caplog.at_level(logging.WARNING):
            vectors, is_fallback = service.embed_texts_with_fallback(
                ["hello", "world"]
            )

        assert is_fallback is True
        assert len(vectors) == 2
        assert all(len(v) == service._dimension for v in vectors)
        assert any(
            "回退" in r.message for r in caplog.records
        ), "回退时未记录 warning 日志"

    def test_fallback_false_on_success(self):
        """API 调用成功时，应返回 ``(vectors, False)``。"""
        dim = 1536
        fake_client = SimpleNamespace(
            embeddings=SimpleNamespace(
                create=lambda input, model: SimpleNamespace(
                    data=[SimpleNamespace(embedding=[0.5] * dim) for _ in input]
                )
            )
        )
        service = EmbeddingService()
        service._get_client = lambda: fake_client

        vectors, is_fallback = service.embed_texts_with_fallback(["hello", "world"])

        assert is_fallback is False
        assert len(vectors) == 2
        assert all(len(v) == dim for v in vectors)
        assert vectors[0] == [0.5] * dim

    def test_embed_texts_backward_compat(self):
        """embed_texts 保持原签名，返回 List[List[float]]。"""
        service = EmbeddingService()
        service._get_client = lambda: None  # 走本地回退

        vectors = service.embed_texts(["a", "b", "c"])

        assert isinstance(vectors, list)
        assert all(isinstance(v, list) for v in vectors)
        assert all(isinstance(x, float) for v in vectors for x in v)
        assert len(vectors) == 3

    def test_embed_texts_with_fallback_empty_list(self):
        """空文本列表应返回 ``([], False)``，不触发任何异常或回退。"""
        service = EmbeddingService()
        service._get_client = lambda: MagicMock()

        vectors, is_fallback = service.embed_texts_with_fallback([])

        assert vectors == []
        assert is_fallback is False

    def test_check_connectivity_false_without_client(self, caplog):
        """未配置 API Key 时 check_connectivity 返回 False 且不抛异常。"""
        service = EmbeddingService()
        service._get_client = lambda: None

        with caplog.at_level(logging.WARNING):
            result = service.check_connectivity()

        assert result is False
        assert any("未配置" in r.message for r in caplog.records)

    def test_check_connectivity_false_on_api_error_no_raise(self, caplog):
        """API 调用抛异常时 check_connectivity 返回 False 且不向上抛出。"""
        boom = RuntimeError("network unreachable")
        fake_client = SimpleNamespace(
            embeddings=SimpleNamespace(create=MagicMock(side_effect=boom))
        )
        service = EmbeddingService()
        service._get_client = lambda: fake_client

        with caplog.at_level(logging.WARNING):
            result = service.check_connectivity()  # 不应抛异常

        assert result is False
        assert any("连通性" in r.message for r in caplog.records)

    def test_check_connectivity_true_on_success(self):
        """API 可达时 check_connectivity 返回 True。"""
        fake_client = SimpleNamespace(
            embeddings=SimpleNamespace(
                create=MagicMock(return_value=SimpleNamespace(data=[]))
            )
        )
        service = EmbeddingService()
        service._get_client = lambda: fake_client

        assert service.check_connectivity() is True

    async def test_main_lifespan_runs_check_connectivity(self, monkeypatch):
        """main.py 的 lifespan 应调用 embedding 服务的 check_connectivity，
        且其返回值不阻止应用启动。"""
        from app.main import create_app, lifespan

        fake_emb = MagicMock()
        fake_emb.check_connectivity.return_value = False
        fake_registry = MagicMock()
        fake_registry.list_skills.return_value = []

        monkeypatch.setattr(
            "app.services.embedding_service.get_embedding_service",
            lambda: fake_emb,
        )
        monkeypatch.setattr("app.main.init_preset_users", MagicMock())
        monkeypatch.setattr("app.main.get_chroma_client", MagicMock())
        monkeypatch.setattr(
            "app.main.get_skill_registry", lambda: fake_registry
        )
        monkeypatch.setattr(
            "app.seed.init_data.init_seed_data", AsyncMock()
        )

        app = create_app()
        # 进入 lifespan 的启动阶段，验证不抛异常且 check_connectivity 被调用
        async with lifespan(app):
            pass

        assert fake_emb.check_connectivity.called

    async def test_main_lifespan_check_connectivity_exception_no_block(self, monkeypatch):
        """即使 check_connectivity 自身抛异常，lifespan 也应继续完成启动。"""
        from app.main import create_app, lifespan

        fake_emb = MagicMock()
        fake_emb.check_connectivity.side_effect = RuntimeError("boom")
        fake_registry = MagicMock()
        fake_registry.list_skills.return_value = []

        monkeypatch.setattr(
            "app.services.embedding_service.get_embedding_service",
            lambda: fake_emb,
        )
        monkeypatch.setattr("app.main.init_preset_users", MagicMock())
        monkeypatch.setattr("app.main.get_chroma_client", MagicMock())
        monkeypatch.setattr(
            "app.main.get_skill_registry", lambda: fake_registry
        )
        monkeypatch.setattr(
            "app.seed.init_data.init_seed_data", AsyncMock()
        )

        app = create_app()
        # 若异常未被捕获，这里会抛出并导致测试失败
        async with lifespan(app):
            pass
