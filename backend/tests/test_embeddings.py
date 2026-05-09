from __future__ import annotations

import pytest

from app.config import Settings
from app.embeddings import EmbeddingClient, EmbeddingClientError


class FakeEmbeddingItem:
    def __init__(self, embedding):
        self.embedding = embedding


class FakeEmbeddingResponse:
    def __init__(self, embeddings):
        self.data = [FakeEmbeddingItem(embedding) for embedding in embeddings]


class FakeEmbeddingsResource:
    def __init__(self, embeddings):
        self.embeddings = embeddings
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeEmbeddingResponse(self.embeddings)


class FakeOpenAIClient:
    def __init__(self, embeddings):
        self.embeddings = FakeEmbeddingsResource(embeddings)


def test_embedding_client_uses_openai_compatible_embeddings_endpoint():
    fake_client = FakeOpenAIClient([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
    settings = Settings(
        OPENAI_API_KEY="sk-test",
        EMBEDDING_MODEL="embedding-test",
        EMBEDDING_DIMENSIONS=3,
    )
    client = EmbeddingClient(settings, client=fake_client)

    embeddings = client.embed_texts(["one", "two"])

    assert embeddings == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    assert fake_client.embeddings.calls[0]["model"] == "embedding-test"
    assert fake_client.embeddings.calls[0]["input"] == ["one", "two"]
    assert fake_client.embeddings.calls[0]["dimensions"] == 3


def test_embedding_client_is_disabled_without_explicit_model():
    settings = Settings(OPENAI_API_KEY="sk-test", EMBEDDING_MODEL="")
    client = EmbeddingClient(settings, client=FakeOpenAIClient([[0.1]]))

    assert not client.is_enabled
    with pytest.raises(EmbeddingClientError):
        client.embed_texts(["one"])


def test_embedding_client_rejects_unexpected_dimensions():
    fake_client = FakeOpenAIClient([[0.1, 0.2]])
    settings = Settings(
        OPENAI_API_KEY="sk-test",
        EMBEDDING_MODEL="embedding-test",
        EMBEDDING_DIMENSIONS=3,
    )
    client = EmbeddingClient(settings, client=fake_client)

    with pytest.raises(EmbeddingClientError):
        client.embed_texts(["one"])
