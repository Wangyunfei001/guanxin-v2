"""上传大小限制测试。

覆盖 max_upload_size_mb 真正生效、超限返回 413 且不落盘。
"""

import io

import pytest

from app.config import settings


@pytest.fixture
def small_upload_limit(monkeypatch):
    """把上传上限临时压到 1 MB，便于用小文件触发超限。"""
    monkeypatch.setattr(settings, "max_upload_size_mb", 1)
    return 1024 * 1024


def _upload(test_client, headers, content: bytes, filename: str = "big.txt"):
    return test_client.post(
        "/api/knowledge/documents/upload",
        headers=headers,
        files={"file": (filename, io.BytesIO(content), "text/plain")},
        data={"title": "超限测试"},
    )


class TestUploadLimit:
    """上传限额行为。"""

    def test_oversized_upload_returns_413(self, test_client, admin_headers, small_upload_limit):
        """超过上限的请求返回 413。"""
        response = _upload(test_client, admin_headers, b"a" * (small_upload_limit + 1024))
        assert response.status_code == 413
        assert "上限" in response.json()["detail"]

    def test_oversized_upload_persists_nothing(
        self, test_client, admin_headers, small_upload_limit
    ):
        """超限请求不会在上传目录留下任何文件。"""
        upload_dir = settings.upload_path
        before = {item.name for item in upload_dir.iterdir()}

        _upload(test_client, admin_headers, b"a" * (small_upload_limit + 1024))

        after = {item.name for item in upload_dir.iterdir()}
        assert after == before

    def test_upload_within_limit_succeeds(self, test_client, admin_headers, small_upload_limit):
        """限额内的文件正常入库。"""
        payload = ("观心测试文档。" + "内容" * 100).encode("utf-8")
        assert len(payload) < small_upload_limit

        response = _upload(test_client, admin_headers, payload, "within-limit.txt")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["filename"] == "within-limit.txt"

        # 清理：删除刚上传的文档，避免影响其他用例
        doc_id = data["data"]["doc_id"]
        test_client.delete(f"/api/knowledge/documents/{doc_id}", headers=admin_headers)

    def test_limit_is_configurable_and_enforced(self, test_client, admin_headers, monkeypatch):
        """上限来自配置，不是硬编码常量。"""
        monkeypatch.setattr(settings, "max_upload_size_mb", 1)
        response = _upload(test_client, admin_headers, b"a" * (2 * 1024 * 1024))
        assert response.status_code == 413

        monkeypatch.setattr(settings, "max_upload_size_mb", 64)
        response = _upload(test_client, admin_headers, b"a" * (2 * 1024 * 1024))
        assert response.status_code == 200
        doc_id = response.json()["data"]["doc_id"]
        test_client.delete(f"/api/knowledge/documents/{doc_id}", headers=admin_headers)
