from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import main as main_module
from app.config import Settings
from app.database import Base
from app.models import KnowledgeChunk, KnowledgeDocument, RagImportJob, now_utc
from app.rag_import_jobs import run_rag_import_job


ADMIN_HEADERS = {"X-Admin-Token": "secret"}


def build_session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def build_admin_client(db, *, upload_dir: Path, token: str = "secret") -> TestClient:
    def override_db():
        yield db

    main_module.app.dependency_overrides[main_module.get_db] = override_db
    main_module.app.dependency_overrides[main_module.get_settings] = lambda: Settings(
        ADMIN_API_TOKEN=token,
        RAG_IMPORT_UPLOAD_DIR=str(upload_dir),
        REDIS_URL="redis://localhost:6379/9",
    )
    return TestClient(main_module.app)


def test_import_upload_requires_admin_token(tmp_path, monkeypatch):
    db = build_session_factory()()
    client = build_admin_client(db, upload_dir=tmp_path)
    monkeypatch.setattr("app.rag_import_jobs.enqueue_import_job", lambda job_id, settings: "queue-1")
    try:
        response = client.post(
            "/api/admin/rag/imports/upload",
            data={"collectionTitle": "RAG 知识库"},
            files={"file": ("note.md", b"# RAG\ncontent", "text/markdown")},
        )
    finally:
        main_module.app.dependency_overrides.clear()
        client.close()

    assert response.status_code == 401
    assert response.json()["code"] == "admin_auth_invalid"


def test_import_upload_rejects_invalid_extension(tmp_path, monkeypatch):
    db = build_session_factory()()
    client = build_admin_client(db, upload_dir=tmp_path)
    monkeypatch.setattr("app.rag_import_jobs.enqueue_import_job", lambda job_id, settings: "queue-1")
    try:
        response = client.post(
            "/api/admin/rag/imports/upload",
            headers=ADMIN_HEADERS,
            data={"collectionTitle": "RAG 知识库"},
            files={"file": ("note.docx", b"content", "application/octet-stream")},
        )
    finally:
        main_module.app.dependency_overrides.clear()
        client.close()

    assert response.status_code == 400
    assert response.json()["code"] == "rag_import_invalid_file"


def test_import_upload_creates_queued_job_and_saves_file(tmp_path, monkeypatch):
    db = build_session_factory()()
    client = build_admin_client(db, upload_dir=tmp_path)
    monkeypatch.setattr("app.rag_import_jobs.enqueue_import_job", lambda job_id, settings: "queue-1")
    try:
        response = client.post(
            "/api/admin/rag/imports/upload",
            headers=ADMIN_HEADERS,
            data={
                "collectionTitle": "RAG 知识库",
                "title": "测试文档",
                "chunkSize": "800",
                "chunkOverlap": "80",
            },
            files={"file": ("note.md", b"# RAG\ncontent", "text/markdown")},
        )
        list_response = client.get("/api/admin/rag/imports", headers=ADMIN_HEADERS)
    finally:
        main_module.app.dependency_overrides.clear()
        client.close()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["queueJobId"] == "queue-1"
    assert payload["collectionTitle"] == "RAG 知识库"
    assert payload["documentTitle"] == "测试文档"
    assert Path(payload["sourceUri"]).exists()
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1


def test_import_retry_requeues_unfinished_jobs(tmp_path, monkeypatch):
    db = build_session_factory()()
    failed = RagImportJob(
        status="failed",
        source_type="upload",
        source_uri=str(tmp_path / "failed.md"),
        file_name="failed.md",
        collection_title="RAG 知识库",
        error_message="boom",
    )
    running = RagImportJob(
        status="running",
        source_type="upload",
        source_uri=str(tmp_path / "running.md"),
        file_name="running.md",
        collection_title="RAG 知识库",
    )
    queued = RagImportJob(
        status="queued",
        source_type="upload",
        source_uri=str(tmp_path / "queued.md"),
        file_name="queued.md",
        collection_title="RAG 知识库",
    )
    succeeded = RagImportJob(
        status="succeeded",
        source_type="upload",
        source_uri=str(tmp_path / "succeeded.md"),
        file_name="succeeded.md",
        collection_title="RAG 知识库",
    )
    db.add_all([failed, running, queued, succeeded])
    db.commit()
    client = build_admin_client(db, upload_dir=tmp_path)
    monkeypatch.setattr("app.rag_import_jobs.enqueue_import_job", lambda job_id, settings: "queue-retry")
    try:
        ok = client.post(f"/api/admin/rag/imports/{failed.id}/retry", headers=ADMIN_HEADERS)
        running_ok = client.post(f"/api/admin/rag/imports/{running.id}/retry", headers=ADMIN_HEADERS)
        queued_ok = client.post(f"/api/admin/rag/imports/{queued.id}/retry", headers=ADMIN_HEADERS)
        rejected = client.post(f"/api/admin/rag/imports/{succeeded.id}/retry", headers=ADMIN_HEADERS)
    finally:
        main_module.app.dependency_overrides.clear()
        client.close()

    assert ok.status_code == 200
    assert ok.json()["status"] == "queued"
    assert ok.json()["queueJobId"] == "queue-retry"
    assert ok.json()["errorMessage"] == ""
    assert running_ok.status_code == 200
    assert running_ok.json()["status"] == "queued"
    assert queued_ok.status_code == 200
    assert queued_ok.json()["status"] == "queued"
    assert rejected.status_code == 400
    assert rejected.json()["code"] == "rag_import_retry_not_allowed"


def test_import_health_requires_admin_token(tmp_path):
    db = build_session_factory()()
    client = build_admin_client(db, upload_dir=tmp_path)
    try:
        response = client.get("/api/admin/rag/imports/health")
    finally:
        main_module.app.dependency_overrides.clear()
        client.close()

    assert response.status_code == 401
    assert response.json()["code"] == "admin_auth_invalid"


def test_import_health_returns_queue_and_worker_info(tmp_path, monkeypatch):
    db = build_session_factory()()
    client = build_admin_client(db, upload_dir=tmp_path)

    class FakeRedis:
        def ping(self):
            return True

    class FakeQueue:
        def __init__(self, name, connection):
            self.name = name
            self.connection = connection
            self.count = 3

    def fake_worker_count(*, connection, queue):
        assert queue.name == "rag-imports"
        return 2

    monkeypatch.setattr("redis.Redis.from_url", lambda url: FakeRedis())
    monkeypatch.setattr("rq.Queue", FakeQueue)
    monkeypatch.setattr("rq.Worker.count", fake_worker_count)

    try:
        response = client.get("/api/admin/rag/imports/health", headers=ADMIN_HEADERS)
    finally:
        main_module.app.dependency_overrides.clear()
        client.close()

    assert response.status_code == 200
    payload = response.json()
    assert payload["redisOk"] is True
    assert payload["queueName"] == "rag-imports"
    assert payload["queuedCount"] == 3
    assert payload["workerCount"] == 2
    assert payload["staleQueuedCount"] == 0
    assert payload["staleRunningCount"] == 0
    assert payload["errorMessage"] is None


def test_import_health_returns_structured_error_when_redis_unavailable(tmp_path, monkeypatch):
    db = build_session_factory()()
    client = build_admin_client(db, upload_dir=tmp_path)

    def fail_from_url(url):
        raise RuntimeError("redis unavailable")

    monkeypatch.setattr("redis.Redis.from_url", fail_from_url)

    try:
        response = client.get("/api/admin/rag/imports/health", headers=ADMIN_HEADERS)
    finally:
        main_module.app.dependency_overrides.clear()
        client.close()

    assert response.status_code == 200
    payload = response.json()
    assert payload["redisOk"] is False
    assert payload["queuedCount"] == 0
    assert payload["workerCount"] == 0
    assert "redis unavailable" in payload["errorMessage"]


def test_import_health_counts_stale_queued_jobs(tmp_path, monkeypatch):
    db = build_session_factory()()
    fresh = RagImportJob(
        status="queued",
        source_type="upload",
        source_uri=str(tmp_path / "fresh.md"),
        file_name="fresh.md",
        collection_title="RAG 知识库",
        created_at=now_utc() - timedelta(minutes=5),
    )
    stale = RagImportJob(
        status="queued",
        source_type="upload",
        source_uri=str(tmp_path / "stale.md"),
        file_name="stale.md",
        collection_title="RAG 知识库",
        created_at=now_utc() - timedelta(minutes=11),
    )
    db.add_all([fresh, stale])
    db.commit()
    client = build_admin_client(db, upload_dir=tmp_path)

    class FakeRedis:
        def ping(self):
            return True

    class FakeQueue:
        def __init__(self, name, connection):
            self.count = 0

    monkeypatch.setattr("redis.Redis.from_url", lambda url: FakeRedis())
    monkeypatch.setattr("rq.Queue", FakeQueue)
    monkeypatch.setattr("rq.Worker.count", lambda *, connection, queue: 0)

    try:
        health = client.get("/api/admin/rag/imports/health", headers=ADMIN_HEADERS)
        listing = client.get("/api/admin/rag/imports", headers=ADMIN_HEADERS)
    finally:
        main_module.app.dependency_overrides.clear()
        client.close()

    assert health.status_code == 200
    assert health.json()["staleQueuedCount"] == 1
    items = listing.json()["items"]
    stale_item = next(item for item in items if item["fileName"] == "stale.md")
    fresh_item = next(item for item in items if item["fileName"] == "fresh.md")
    assert stale_item["isStale"] is True
    assert fresh_item["isStale"] is False


def test_import_health_counts_stale_running_jobs(tmp_path, monkeypatch):
    db = build_session_factory()()
    fresh = RagImportJob(
        status="running",
        source_type="upload",
        source_uri=str(tmp_path / "fresh-running.md"),
        file_name="fresh-running.md",
        collection_title="RAG 知识库",
        started_at=now_utc() - timedelta(minutes=20),
    )
    stale = RagImportJob(
        status="running",
        source_type="upload",
        source_uri=str(tmp_path / "stale-running.md"),
        file_name="stale-running.md",
        collection_title="RAG 知识库",
        started_at=now_utc() - timedelta(minutes=31),
    )
    db.add_all([fresh, stale])
    db.commit()
    client = build_admin_client(db, upload_dir=tmp_path)

    class FakeRedis:
        def ping(self):
            return True

    class FakeQueue:
        def __init__(self, name, connection):
            self.count = 0

    monkeypatch.setattr("redis.Redis.from_url", lambda url: FakeRedis())
    monkeypatch.setattr("rq.Queue", FakeQueue)
    monkeypatch.setattr("rq.Worker.count", lambda *, connection, queue: 0)

    try:
        health = client.get("/api/admin/rag/imports/health", headers=ADMIN_HEADERS)
        listing = client.get("/api/admin/rag/imports", headers=ADMIN_HEADERS)
    finally:
        main_module.app.dependency_overrides.clear()
        client.close()

    assert health.status_code == 200
    assert health.json()["staleRunningCount"] == 1
    items = listing.json()["items"]
    stale_item = next(item for item in items if item["fileName"] == "stale-running.md")
    fresh_item = next(item for item in items if item["fileName"] == "fresh-running.md")
    assert stale_item["isStale"] is True
    assert fresh_item["isStale"] is False


def test_worker_imports_document_and_marks_success(tmp_path, monkeypatch):
    session_factory = build_session_factory()
    db = session_factory()
    file_path = tmp_path / "worker.md"
    file_path.write_text("RAG worker import content", encoding="utf-8")
    job = RagImportJob(
        status="queued",
        source_type="upload",
        source_uri=str(file_path),
        file_name="worker.md",
        collection_title="RAG 知识库",
        document_title="Worker 文档",
        chunk_size=800,
        chunk_overlap=80,
    )
    db.add(job)
    db.commit()
    job_id = job.id
    db.close()
    monkeypatch.setattr("app.rag_import_jobs.SessionLocal", session_factory)
    monkeypatch.setattr(
        "app.curated_import.get_settings",
        lambda: Settings(EMBEDDING_MODEL="", EMBEDDING_API_KEY=""),
    )

    run_rag_import_job(job_id)

    db = session_factory()
    saved = db.get(RagImportJob, job_id)
    assert saved.status == "succeeded"
    assert saved.stats_json["total_imported"] == 1
    assert db.query(KnowledgeDocument).filter_by(title="Worker 文档").count() == 1
    assert db.query(KnowledgeChunk).filter(KnowledgeChunk.title.like("Worker 文档%")).count() == 1


def test_worker_marks_failed_when_import_raises(tmp_path, monkeypatch):
    session_factory = build_session_factory()
    db = session_factory()
    job = RagImportJob(
        status="queued",
        source_type="upload",
        source_uri=str(tmp_path / "missing.md"),
        file_name="missing.md",
        collection_title="RAG 知识库",
    )
    db.add(job)
    db.commit()
    job_id = job.id
    db.close()
    monkeypatch.setattr("app.rag_import_jobs.SessionLocal", session_factory)

    def fail_import(*args, **kwargs):
        raise RuntimeError("import failed")

    monkeypatch.setattr("app.rag_import_jobs.import_document_file_with_stats", fail_import)

    try:
        run_rag_import_job(job_id)
    except RuntimeError:
        pass

    db = session_factory()
    saved = db.get(RagImportJob, job_id)
    assert saved.status == "failed"
    assert "import failed" in saved.error_message
