from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import main as main_module
from app.config import Settings
from app.database import Base
from app.models import KnowledgeChunk, KnowledgeCollection, KnowledgeDocument, QuestionBankItem


ADMIN_HEADERS = {"X-Admin-Token": "secret"}


class FakeEmbeddingClient:
    is_enabled = True
    model_name = "fake-admin-embedding"
    version = "admin-embedding-v1"

    def embed_query(self, text: str) -> list[float]:
        values = [0.0] * 1536
        values[0] = 1.0
        return values


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


def admin_settings(token: str = "secret", app_env: str = "development") -> Settings:
    return Settings(ADMIN_API_TOKEN=token, APP_ENV=app_env)


def build_admin_client(
    db,
    *,
    token: str = "secret",
    app_env: str = "development",
    embedding_client=None,
) -> TestClient:
    def override_db():
        yield db

    main_module.app.dependency_overrides[main_module.get_db] = override_db
    main_module.app.dependency_overrides[main_module.get_settings] = (
        lambda: admin_settings(token, app_env)
    )
    if embedding_client is not None:
        main_module.app.dependency_overrides[main_module.get_admin_embedding_client] = (
            lambda: embedding_client
        )
    return TestClient(main_module.app)


def seed_rag_data(db):
    collection = KnowledgeCollection(
        title="Admin RAG",
        description="Admin test collection",
        source_type="curated",
        tags_json=["RAG"],
    )
    db.add(collection)
    db.flush()
    document = KnowledgeDocument(
        collection_id=collection.id,
        title="Admin document",
        source_type="markdown",
        source_uri="admin.md",
        metadata_json={"owner": "test"},
        status="active",
        is_active=True,
    )
    db.add(document)
    db.flush()
    chunk = KnowledgeChunk(
        collection_id=collection.id,
        document_id=document.id,
        title="Admin chunk",
        content="Admin chunk content about RAG management.",
        source_ref="admin.md",
        tags_json=["RAG"],
        is_active=True,
        embedding=[1.0] + [0.0] * 1535,
        embedding_model="old-model",
        embedding_version="old-version",
        content_hash="old-hash",
    )
    question = QuestionBankItem(
        collection_id=collection.id,
        stem="Admin question?",
        options_json=["A", "B", "C", "D"],
        answer_index=0,
        answer_indexes_json=[0],
        question_type="single_choice",
        explanation="Admin explanation",
        knowledge_point="Admin point",
        difficulty="normal",
        tags_json=["RAG"],
        is_active=True,
        embedding=[1.0] + [0.0] * 1535,
        embedding_model="old-model",
        embedding_version="old-version",
        content_hash="old-hash",
    )
    db.add_all([chunk, question])
    db.commit()
    return collection, document, chunk, question


def test_admin_api_is_disabled_without_token():
    db = build_db()
    client = build_admin_client(db, token="")
    try:
        response = client.get("/api/admin/rag/collections", headers=ADMIN_HEADERS)
    finally:
        main_module.app.dependency_overrides.clear()
        client.close()

    assert response.status_code == 404
    assert response.json()["code"] == "admin_disabled"


def test_admin_api_rejects_missing_or_wrong_token():
    db = build_db()
    client = build_admin_client(db)
    try:
        missing = client.get("/api/admin/rag/collections")
        wrong = client.get("/api/admin/rag/collections", headers={"X-Admin-Token": "wrong"})
    finally:
        main_module.app.dependency_overrides.clear()
        client.close()

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert wrong.json()["code"] == "admin_auth_invalid"


def test_rag_debug_api_allows_development_without_token():
    db = build_db()
    seed_rag_data(db)
    client = build_admin_client(db, token="", embedding_client=FakeEmbeddingClient())
    try:
        response = client.post("/api/debug/rag", json={"query": "RAG management"})
    finally:
        main_module.app.dependency_overrides.clear()
        client.close()

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "RAG management"
    assert payload["retrievalVersion"] == "hybrid-rag-v1.3"
    assert payload["chunks"][0]["title"] == "Admin chunk"
    assert "keywordScoreBreakdown" in payload["chunks"][0]


def test_rag_debug_api_requires_admin_token_outside_development():
    db = build_db()
    seed_rag_data(db)
    client = build_admin_client(db, app_env="production", embedding_client=FakeEmbeddingClient())
    try:
        missing = client.post("/api/debug/rag", json={"query": "RAG management"})
        wrong = client.post(
            "/api/debug/rag",
            headers={"X-Admin-Token": "wrong"},
            json={"query": "RAG management"},
        )
        ok = client.post(
            "/api/debug/rag",
            headers=ADMIN_HEADERS,
            json={"query": "RAG management", "limit": 3},
        )
    finally:
        main_module.app.dependency_overrides.clear()
        client.close()

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert wrong.json()["code"] == "admin_auth_invalid"
    assert ok.status_code == 200
    assert len(ok.json()["chunks"]) <= 3


def test_rag_debug_api_validation_errors():
    db = build_db()
    client = build_admin_client(db)
    try:
        empty_query = client.post("/api/debug/rag", json={"query": "   "})
        bad_limit = client.post("/api/debug/rag", json={"query": "RAG", "limit": 21})
    finally:
        main_module.app.dependency_overrides.clear()
        client.close()

    assert empty_query.status_code == 422
    assert bad_limit.status_code == 422


def test_admin_collections_list_returns_counts():
    db = build_db()
    seed_rag_data(db)
    client = build_admin_client(db)
    try:
        response = client.get("/api/admin/rag/collections", headers=ADMIN_HEADERS)
    finally:
        main_module.app.dependency_overrides.clear()
        client.close()

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["title"] == "Admin RAG"
    assert item["documentCount"] == 1
    assert item["chunkCount"] == 1
    assert item["questionCount"] == 1


def test_admin_lists_support_filters_and_update_document():
    db = build_db()
    collection, document, chunk, _ = seed_rag_data(db)
    client = build_admin_client(db)
    try:
        documents = client.get(
            f"/api/admin/rag/documents?collectionId={collection.id}&q=Admin",
            headers=ADMIN_HEADERS,
        )
        chunks = client.get(
            f"/api/admin/rag/chunks?documentId={document.id}&q=management",
            headers=ADMIN_HEADERS,
        )
        updated = client.patch(
            f"/api/admin/rag/documents/{document.id}",
            headers=ADMIN_HEADERS,
            json={"title": "Updated document", "status": "inactive", "metadata": {"owner": "admin"}},
        )
    finally:
        main_module.app.dependency_overrides.clear()
        client.close()

    assert documents.status_code == 200
    assert documents.json()["total"] == 1
    assert chunks.status_code == 200
    assert chunks.json()["items"][0]["id"] == chunk.id
    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated document"
    assert updated.json()["status"] == "inactive"
    assert updated.json()["metadata"] == {"owner": "admin"}


def test_admin_patch_chunk_clears_embedding_and_not_found_returns_404():
    db = build_db()
    _, _, chunk, _ = seed_rag_data(db)
    client = build_admin_client(db)
    try:
        response = client.patch(
            f"/api/admin/rag/chunks/{chunk.id}",
            headers=ADMIN_HEADERS,
            json={"content": "Changed admin chunk content.", "tags": ["updated"]},
        )
        missing = client.get("/api/admin/rag/chunks/not-found", headers=ADMIN_HEADERS)
    finally:
        main_module.app.dependency_overrides.clear()
        client.close()

    assert response.status_code == 200
    assert response.json()["content"] == "Changed admin chunk content."
    refreshed = db.get(KnowledgeChunk, chunk.id)
    assert refreshed.embedding is None
    assert refreshed.embedding_model is None
    assert refreshed.content_hash is None
    assert missing.status_code == 404
    assert missing.json()["code"] == "rag_admin_not_found"


def test_admin_reembed_chunk_and_question():
    db = build_db()
    _, _, chunk, question = seed_rag_data(db)
    client = build_admin_client(db, embedding_client=FakeEmbeddingClient())
    try:
        chunk_response = client.post(
            f"/api/admin/rag/chunks/{chunk.id}/reembed",
            headers=ADMIN_HEADERS,
        )
        question_response = client.post(
            f"/api/admin/rag/questions/{question.id}/reembed",
            headers=ADMIN_HEADERS,
        )
    finally:
        main_module.app.dependency_overrides.clear()
        client.close()

    assert chunk_response.status_code == 200
    assert chunk_response.json()["embeddingModel"] == "fake-admin-embedding"
    assert question_response.status_code == 200
    assert question_response.json()["embeddingVersion"] == "admin-embedding-v1"
    assert db.get(KnowledgeChunk, chunk.id).content_hash != "old-hash"
    assert db.get(QuestionBankItem, question.id).content_hash != "old-hash"


def test_admin_reembed_returns_error_when_embedding_disabled():
    db = build_db()
    _, _, chunk, _ = seed_rag_data(db)
    client = build_admin_client(db, embedding_client=DisabledEmbeddingClient())
    try:
        response = client.post(f"/api/admin/rag/chunks/{chunk.id}/reembed", headers=ADMIN_HEADERS)
    finally:
        main_module.app.dependency_overrides.clear()
        client.close()

    assert response.status_code == 400
    assert response.json()["code"] == "embedding_disabled"


def test_admin_patch_question_clears_embedding_and_lists_questions():
    db = build_db()
    collection, _, _, question = seed_rag_data(db)
    client = build_admin_client(db)
    try:
        listed = client.get(
            f"/api/admin/rag/questions?collectionId={collection.id}&q=Admin",
            headers=ADMIN_HEADERS,
        )
        updated = client.patch(
            f"/api/admin/rag/questions/{question.id}",
            headers=ADMIN_HEADERS,
            json={"difficulty": "hard", "tags": ["admin"]},
        )
    finally:
        main_module.app.dependency_overrides.clear()
        client.close()

    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert updated.status_code == 200
    assert updated.json()["difficulty"] == "hard"
    refreshed = db.get(QuestionBankItem, question.id)
    assert refreshed.tags_json == ["admin"]
    assert refreshed.embedding is None
    assert refreshed.content_hash is None
