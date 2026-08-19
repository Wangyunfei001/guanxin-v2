"""知识库 API 测试。"""

import io
import pytest


class TestKnowledge:
    """知识库 API 测试套件。"""

    def test_list_documents(self, test_client, admin_headers):
        """测试列出文档。"""
        response = test_client.get("/api/knowledge/documents", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert isinstance(data["data"], list)

    def test_upload_document(self, test_client, admin_headers):
        """测试上传文档。"""
        content = "这是一个测试文档。用于验证文档上传功能是否正常工作。" * 10
        response = test_client.post(
            "/api/knowledge/documents/upload",
            headers=admin_headers,
            files={"file": ("test_upload.txt", io.BytesIO(content.encode("utf-8")), "text/plain")},
            data={"title": "测试上传文档"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["filename"] == "test_upload.txt"
        assert data["data"]["status"] == "ready"
        assert data["data"]["chunk_count"] > 0

    def test_retrieve(self, test_client, admin_headers):
        """测试知识库检索。"""
        # 先上传一个文档
        content = "人工智能是计算机科学的一个分支，它致力于研究、开发用于模拟、延伸和扩展人类智能的理论、方法、技术及应用系统。"
        test_client.post(
            "/api/knowledge/documents/upload",
            headers=admin_headers,
            files={"file": ("ai_intro.txt", io.BytesIO(content.encode("utf-8")), "text/plain")},
            data={"title": "人工智能简介"},
        )

        # 检索
        response = test_client.post(
            "/api/knowledge/retrieve",
            headers=admin_headers,
            json={"query": "人工智能是什么", "top_k": 3},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert isinstance(data["data"], list)
        if data["data"]:
            assert "content" in data["data"][0]
            assert "score" in data["data"][0]

    def test_tenant_isolation(self, test_client, admin_headers, demo_headers):
        """测试租户隔离。"""
        # 租户A上传文档
        content_a = "这是租户A的私有文档，内容关于项目规划。"
        response_a = test_client.post(
            "/api/knowledge/documents/upload",
            headers=admin_headers,
            files={"file": ("tenant_a_doc.txt", io.BytesIO(content_a.encode("utf-8")), "text/plain")},
            data={"title": "租户A文档"},
        )
        assert response_a.status_code == 200
        doc_a = response_a.json()["data"]

        # 租户B列出文档，不应看到租户A的文档
        response_b = test_client.get(
            "/api/knowledge/documents",
            headers=demo_headers,
        )
        assert response_b.status_code == 200
        docs_b = response_b.json()["data"]
        doc_ids_b = [d["doc_id"] for d in docs_b]
        assert doc_a["doc_id"] not in doc_ids_b

        # 租户B检索，不应返回租户A的文档内容
        response_b_retrieve = test_client.post(
            "/api/knowledge/retrieve",
            headers=demo_headers,
            json={"query": "租户A的私有文档", "top_k": 5},
        )
        assert response_b_retrieve.status_code == 200
        results_b = response_b_retrieve.json()["data"]
        for result in results_b:
            assert "租户A的私有文档" not in result.get("content", "")

    def test_delete_document(self, test_client, admin_headers):
        """测试删除文档。"""
        # 先上传
        content = "待删除的测试文档内容。"
        response = test_client.post(
            "/api/knowledge/documents/upload",
            headers=admin_headers,
            files={"file": ("delete_test.txt", io.BytesIO(content.encode("utf-8")), "text/plain")},
            data={"title": "删除测试"},
        )
        doc_id = response.json()["data"]["doc_id"]

        # 删除
        response = test_client.delete(
            f"/api/knowledge/documents/{doc_id}",
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert response.json()["data"]["deleted"] is True

        # 确认已删除
        response = test_client.get(
            f"/api/knowledge/documents/{doc_id}",
            headers=admin_headers,
        )
        assert response.json()["code"] == 4041

    def test_get_document_detail(self, test_client, admin_headers):
        """测试获取文档详情。"""
        # 上传文档
        content = "文档详情测试内容。" * 5
        response = test_client.post(
            "/api/knowledge/documents/upload",
            headers=admin_headers,
            files={"file": ("detail_test.txt", io.BytesIO(content.encode("utf-8")), "text/plain")},
            data={"title": "详情测试文档"},
        )
        doc_id = response.json()["data"]["doc_id"]

        # 获取详情
        response = test_client.get(
            f"/api/knowledge/documents/{doc_id}",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["doc_id"] == doc_id
        assert data["data"]["title"] == "详情测试文档"
