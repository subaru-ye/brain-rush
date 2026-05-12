from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.database import Base
from app.document_loaders import load_local_document
from app.document_pipeline import build_document_import_payload, import_document_file_with_stats
from app.models import KnowledgeChunk, KnowledgeCollection, KnowledgeDocument
from app.text_cleaning import clean_text
from app.text_splitters import split_text


class DisabledEmbeddingClient:
    is_enabled = False
    model_name = ""
    version = ""


def build_db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)()


def test_load_text_and_markdown_documents(tmp_path: Path):
    text_path = tmp_path / "notes.txt"
    markdown_path = tmp_path / "guide.md"
    text_path.write_text("纯文本资料", encoding="utf-8")
    markdown_path.write_text("# 标题\n\nMarkdown 资料", encoding="utf-8")

    text_doc = load_local_document(text_path)
    markdown_doc = load_local_document(markdown_path)

    assert text_doc.source_type == "txt"
    assert text_doc.text == "纯文本资料"
    assert markdown_doc.source_type == "markdown"
    assert "Markdown 资料" in markdown_doc.text


def test_load_pdf_document_extracts_text(tmp_path: Path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(_sample_pdf_bytes())

    loaded = load_local_document(pdf_path)

    assert loaded.source_type == "pdf"
    assert loaded.metadata["pageCount"] == 1
    assert "Pipeline PDF text" in loaded.text


def test_clean_text_removes_extra_blank_lines_and_spaces():
    raw = " 第一行  \r\n\r\n\r\n 第二\t\t行 \n   \n第三行"

    assert clean_text(raw) == "第一行\n\n第二 行\n\n第三行"


def test_split_text_returns_chunks_with_overlap():
    text = "\n\n".join(["A" * 20, "B" * 20, "C" * 20])

    chunks = split_text(text, chunk_size=35, chunk_overlap=5)

    assert len(chunks) == 3
    assert chunks[1].startswith(chunks[0][-5:])
    assert all(chunk.strip() for chunk in chunks)


def test_document_pipeline_builds_curated_payload(tmp_path: Path):
    path = tmp_path / "rag.md"
    path.write_text("第一段 RAG Pipeline。\n\n第二段 document chunk。", encoding="utf-8")

    payload = build_document_import_payload(
        path,
        collection_title="RAG 知识库",
        chunk_size=20,
        chunk_overlap=5,
    )

    document = payload["collections"][0]["documents"][0]
    assert payload["collections"][0]["title"] == "RAG 知识库"
    assert document["title"] == "rag.md"
    assert document["sourceType"] == "markdown"
    assert document["sourceUri"] == str(path.resolve())
    assert document["metadata"]["chunkSize"] == 20
    assert document["chunks"]


def test_document_pipeline_imports_document_and_chunks(tmp_path: Path):
    db = build_db()
    path = tmp_path / "source.txt"
    path.write_text("RAG document pipeline import content.", encoding="utf-8")

    first = import_document_file_with_stats(
        db,
        path,
        collection_title="Pipeline Collection",
        embedding_client=DisabledEmbeddingClient(),
    )
    second = import_document_file_with_stats(
        db,
        path,
        collection_title="Pipeline Collection",
        embedding_client=DisabledEmbeddingClient(),
    )

    document = db.query(KnowledgeDocument).one()
    chunk = db.query(KnowledgeChunk).one()
    assert first.total_imported == 1
    assert second.total_imported == 1
    assert db.query(KnowledgeCollection).count() == 1
    assert db.query(KnowledgeDocument).count() == 1
    assert db.query(KnowledgeChunk).count() == 1
    assert document.source_type == "txt"
    assert document.source_uri == str(path.resolve())
    assert chunk.document_id == document.id


def test_document_pipeline_updates_content_hash_when_file_changes(tmp_path: Path):
    db = build_db()
    path = tmp_path / "mutable.txt"
    path.write_text("Original document pipeline content.", encoding="utf-8")
    import_document_file_with_stats(
        db,
        path,
        collection_title="Pipeline Collection",
        embedding_client=DisabledEmbeddingClient(),
    )
    original_hash = db.query(KnowledgeChunk).one().content_hash

    path.write_text("Changed document pipeline content.", encoding="utf-8")
    import_document_file_with_stats(
        db,
        path,
        collection_title="Pipeline Collection",
        embedding_client=DisabledEmbeddingClient(),
    )

    chunk = db.query(KnowledgeChunk).one()
    assert chunk.content == "Changed document pipeline content."
    assert chunk.content_hash != original_hash


def _sample_pdf_bytes() -> bytes:
    return b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>
endobj
4 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
5 0 obj
<< /Length 44 >>
stream
BT /F1 24 Tf 100 700 Td (Pipeline PDF text) Tj ET
endstream
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000241 00000 n 
0000000311 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
405
%%EOF
"""
