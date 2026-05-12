from __future__ import annotations

from hashlib import sha256
from typing import Any

from openai import OpenAI

from .config import Settings
from .quiz_answers import format_option_indexes


EMBEDDING_VERSION = "embedding-v1"
EMBEDDING_BATCH_SIZE = 10


class EmbeddingClientError(RuntimeError):
    pass


class EmbeddingClient:
    def __init__(self, settings: Settings, client: Any | None = None):
        self.model_name = settings.embedding_model.strip()
        self.dimensions = settings.embedding_dimensions
        self.version = EMBEDDING_VERSION
        self.api_key = settings.resolved_embedding_api_key
        self.base_url = settings.resolved_embedding_base_url
        self.timeout_seconds = settings.embedding_timeout_seconds
        self.max_retries = settings.embedding_max_retries
        self.client = client

    @property
    def is_enabled(self) -> bool:
        return bool(self.model_name and self.api_key)

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not self.is_enabled:
            raise EmbeddingClientError("Embedding model or API key is not configured")
        if not texts:
            return []

        client = self.client or OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout_seconds,
            max_retries=self.max_retries,
        )
        embeddings: list[list[float]] = []
        for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
            batch = texts[start : start + EMBEDDING_BATCH_SIZE]
            response = client.embeddings.create(
                model=self.model_name,
                input=batch,
                dimensions=self.dimensions,
            )
            embeddings.extend(list(item.embedding) for item in response.data)
        if len(embeddings) != len(texts):
            raise EmbeddingClientError("Embedding response count does not match input count")
        for embedding in embeddings:
            if len(embedding) != self.dimensions:
                raise EmbeddingClientError("Embedding dimensions do not match configuration")
        return embeddings


def content_hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def chunk_embedding_text(chunk: Any) -> str:
    document = getattr(chunk, "document", None)
    return "\n".join(
        [
            f"Collection: {getattr(getattr(chunk, 'collection', None), 'title', '')}",
            f"Collection description: {getattr(getattr(chunk, 'collection', None), 'description', '')}",
            f"Document: {getattr(document, 'title', '')}",
            f"Document source type: {getattr(document, 'source_type', '')}",
            f"Document source URI: {getattr(document, 'source_uri', '')}",
            f"Title: {chunk.title}",
            f"Content: {chunk.content}",
            f"Source: {chunk.source_ref}",
            f"Tags: {', '.join(chunk.tags_json or [])}",
        ]
    )


def question_embedding_text(item: Any) -> str:
    answer_indexes = item.answer_indexes_json or [item.answer_index]
    options = [str(option) for option in item.options_json]
    return "\n".join(
        [
            f"Collection: {getattr(getattr(item, 'collection', None), 'title', '')}",
            f"Collection description: {getattr(getattr(item, 'collection', None), 'description', '')}",
            f"Question: {item.stem}",
            f"Question type: {item.question_type}",
            f"Options: {' | '.join(options)}",
            f"Answer: {format_option_indexes(options, answer_indexes)}",
            f"Explanation: {item.explanation}",
            f"Knowledge point: {item.knowledge_point}",
            f"Difficulty: {item.difficulty}",
            f"Tags: {', '.join(item.tags_json or [])}",
        ]
    )
