from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from .curated_import import ImportStats, import_curated_payload_with_stats
from .document_loaders import load_local_document
from .embeddings import EmbeddingClient
from .text_cleaning import clean_text
from .text_splitters import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE, split_text


def build_document_import_payload(
    path: str | Path,
    *,
    collection_title: str,
    title: str | None = None,
    source_uri: str | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> dict[str, Any]:
    loaded = load_local_document(path)
    document_title = (title or loaded.path.name).strip()
    document_source_uri = (source_uri or str(loaded.path)).strip()
    cleaned_text = clean_text(loaded.text)
    chunks = split_text(cleaned_text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    if not chunks:
        raise ValueError(f"Document does not contain importable chunks: {loaded.path}")

    metadata = {
        **loaded.metadata,
        "chunkSize": chunk_size,
        "chunkOverlap": chunk_overlap,
        "chunkCount": len(chunks),
    }
    return {
        "collections": [
            {
                "title": collection_title,
                "documents": [
                    {
                        "title": document_title,
                        "sourceType": loaded.source_type,
                        "sourceUri": document_source_uri,
                        "metadata": metadata,
                        "chunks": [
                            {
                                "title": f"{document_title} #{index}",
                                "content": chunk,
                            }
                            for index, chunk in enumerate(chunks, start=1)
                        ],
                    }
                ],
            }
        ]
    }


def import_document_file_with_stats(
    db: Session,
    path: str | Path,
    *,
    collection_title: str,
    title: str | None = None,
    source_uri: str | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    embedding_client: EmbeddingClient | None = None,
) -> ImportStats:
    payload = build_document_import_payload(
        path,
        collection_title=collection_title,
        title=title,
        source_uri=source_uri,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return import_curated_payload_with_stats(db, payload, embedding_client=embedding_client)
