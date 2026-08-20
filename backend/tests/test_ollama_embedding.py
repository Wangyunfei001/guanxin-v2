"""Ollama Embedding provider 契约测试。"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.config import settings
from app.services.embedding_service import EmbeddingProviderError, EmbeddingService


@pytest.fixture
def ollama_service(monkeypatch) -> EmbeddingService:
    monkeypatch.setattr(settings, "embedding_provider", "ollama")
    monkeypatch.setattr(settings, "embedding_model", "bge-m3:latest")
    monkeypatch.setattr(settings, "embedding_dimension", 1024)
    monkeypatch.setattr(settings, "ollama_base_url", "http://127.0.0.1:11434")
    monkeypatch.setattr(settings, "openai_api_key", "llm-secret-must-not-be-used")
    monkeypatch.setattr(settings, "embedding_api_key", "remote-secret-must-not-be-used")
    return EmbeddingService()


def _response(vectors):
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"embeddings": vectors}
    return response


def test_ollama_batches_inputs_and_ignores_remote_keys(ollama_service):
    vectors = [[0.1] * 1024, [0.2] * 1024]
    with patch(
        "app.services.embedding_service.httpx.post",
        return_value=_response(vectors),
    ) as post:
        result, is_fallback = ollama_service.embed_texts_with_fallback(
            ["你好", "world"]
        )

    assert result == vectors
    assert is_fallback is False
    assert ollama_service._api_key == ""
    post.assert_called_once_with(
        "http://127.0.0.1:11434/api/embed",
        json={"model": "bge-m3:latest", "input": ["你好", "world"]},
        timeout=120.0,
    )


@pytest.mark.parametrize(
    "vectors,error_text",
    [
        ([[0.1] * 1024], "数量"),
        ([[0.1] * 8, [0.2] * 8], "维度"),
        ([[0.1] * 1024, ["bad"] * 1024], "非数值"),
    ],
)
def test_ollama_rejects_invalid_responses(ollama_service, vectors, error_text):
    with patch(
        "app.services.embedding_service.httpx.post",
        return_value=_response(vectors),
    ), pytest.raises(EmbeddingProviderError, match=error_text):
        ollama_service.embed_texts_with_fallback(["a", "b"])


def test_ollama_failure_does_not_fallback_to_random_vectors(ollama_service):
    request = httpx.Request("POST", "http://127.0.0.1:11434/api/embed")
    with patch(
        "app.services.embedding_service.httpx.post",
        side_effect=httpx.ConnectError("offline", request=request),
    ), pytest.raises(EmbeddingProviderError, match="Ollama"):
        ollama_service.embed_texts_with_fallback(["hello"])


def test_ollama_connectivity_failure_returns_false(ollama_service):
    request = httpx.Request("POST", "http://127.0.0.1:11434/api/embed")
    with patch(
        "app.services.embedding_service.httpx.post",
        side_effect=httpx.ConnectError("offline", request=request),
    ):
        assert ollama_service.check_connectivity() is False


def test_ollama_connectivity_validates_real_vector_shape(ollama_service):
    with patch(
        "app.services.embedding_service.httpx.post",
        return_value=_response([[0.3] * 1024]),
    ):
        assert ollama_service.check_connectivity() is True


def test_local_provider_never_creates_remote_client(monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "local")
    monkeypatch.setattr(settings, "embedding_dimension", 32)
    service = EmbeddingService()

    with patch("app.services.embedding_service.httpx.post") as post:
        vectors, is_fallback = service.embed_texts_with_fallback(["local"])

    assert is_fallback is True
    assert len(vectors[0]) == 32
    assert service.check_connectivity() is True
    post.assert_not_called()
