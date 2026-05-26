from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import Settings
from .database import SessionLocal
from .document_pipeline import import_document_file_with_stats
from .errors import ApiHttpError
from .models import RagImportJob, new_id, now_utc
from .schemas import RagImportJobItem, RagImportJobListResponse


RAG_IMPORT_QUEUE_NAME = "rag-imports"
ALLOWED_UPLOAD_EXTENSIONS = {".txt", ".md", ".pdf"}
RAG_IMPORT_STATUSES = {"queued", "running", "succeeded", "failed"}


async def create_upload_import_job(
    db: Session,
    upload: UploadFile,
    *,
    collection_title: str,
    document_title: str | None,
    chunk_size: int,
    chunk_overlap: int,
    settings: Settings,
) -> RagImportJobItem:
    file_name = Path(upload.filename or "").name.strip()
    if not file_name:
        raise ApiHttpError(400, "rag_import_invalid_file", "上传文件名不能为空")
    extension = Path(file_name).suffix.lower()
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise ApiHttpError(400, "rag_import_invalid_file", "只支持 .txt、.md、.pdf 文件")
    if chunk_overlap >= chunk_size:
        raise ApiHttpError(400, "rag_import_invalid_chunk", "Chunk overlap 必须小于 chunk size")

    job = RagImportJob(
        id=new_id(),
        status="queued",
        source_type="upload",
        file_name=file_name,
        collection_title=collection_title.strip(),
        document_title=(document_title or "").strip() or None,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        stats_json={},
        error_message="",
    )
    db.add(job)
    db.flush()

    upload_dir = Path(settings.rag_import_upload_dir).resolve() / str(job.id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / file_name
    content = await upload.read()
    if not content:
        raise ApiHttpError(400, "rag_import_invalid_file", "上传文件不能为空")
    file_path.write_bytes(content)

    job.source_uri = str(file_path)
    db.commit()
    db.refresh(job)

    try:
        queue_job_id = enqueue_import_job(str(job.id), settings)
    except ApiHttpError as exc:
        job.status = "failed"
        job.error_message = exc.detail
        job.finished_at = now_utc()
        db.commit()
        raise
    job.queue_job_id = queue_job_id
    db.commit()
    db.refresh(job)
    return _job_item(job)


def list_import_jobs(
    db: Session,
    *,
    status: str | None,
    limit: int,
    offset: int,
) -> RagImportJobListResponse:
    stmt = select(RagImportJob)
    if status:
        normalized = status.strip()
        if normalized not in RAG_IMPORT_STATUSES:
            raise ApiHttpError(400, "rag_import_invalid_status", "导入任务状态无效")
        stmt = stmt.where(RagImportJob.status == normalized)

    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    jobs = db.scalars(stmt.order_by(RagImportJob.created_at.desc()).limit(limit).offset(offset)).all()
    return RagImportJobListResponse(
        items=[_job_item(job) for job in jobs],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_import_job(db: Session, job_id: str) -> RagImportJobItem:
    return _job_item(_get_job(db, job_id))


def retry_import_job(db: Session, job_id: str, settings: Settings) -> RagImportJobItem:
    job = _get_job(db, job_id)
    if job.status == "succeeded":
        raise ApiHttpError(400, "rag_import_retry_not_allowed", "已成功的导入任务不能重新入队")
    job.status = "queued"
    job.stats_json = {}
    job.error_message = ""
    job.started_at = None
    job.finished_at = None
    db.commit()
    db.refresh(job)

    queue_job_id = enqueue_import_job(str(job.id), settings)
    job.queue_job_id = queue_job_id
    db.commit()
    db.refresh(job)
    return _job_item(job)


def enqueue_import_job(job_id: str, settings: Settings) -> str:
    try:
        from redis import Redis
        from rq import Queue
    except ImportError as exc:
        raise ApiHttpError(500, "rag_import_queue_unavailable", "导入队列依赖未安装") from exc

    redis = Redis.from_url(settings.redis_url)
    queue = Queue(RAG_IMPORT_QUEUE_NAME, connection=redis)
    job = queue.enqueue(run_rag_import_job, job_id)
    return str(job.id)


def run_rag_import_job(job_id: str) -> None:
    with SessionLocal() as db:
        job = _get_job(db, job_id)
        job.status = "running"
        job.started_at = now_utc()
        job.finished_at = None
        job.error_message = ""
        db.commit()

        try:
            stats = import_document_file_with_stats(
                db,
                job.source_uri,
                collection_title=job.collection_title,
                title=job.document_title,
                source_uri=job.source_uri,
                chunk_size=job.chunk_size,
                chunk_overlap=job.chunk_overlap,
            )
            job = _get_job(db, job_id)
            job.status = "succeeded"
            job.stats_json = asdict(stats)
            job.error_message = ""
            job.finished_at = now_utc()
            db.commit()
        except Exception as exc:
            db.rollback()
            job = _get_job(db, job_id)
            job.status = "failed"
            job.error_message = str(exc)
            job.finished_at = now_utc()
            db.commit()
            raise


def _get_job(db: Session, job_id: str) -> RagImportJob:
    job = db.get(RagImportJob, job_id)
    if not job:
        raise ApiHttpError(404, "rag_import_not_found", "导入任务不存在")
    return job


def _job_item(job: RagImportJob) -> RagImportJobItem:
    return RagImportJobItem(
        id=str(job.id),
        status=job.status,
        sourceType=job.source_type,
        sourceUri=job.source_uri,
        fileName=job.file_name,
        collectionTitle=job.collection_title,
        documentTitle=job.document_title,
        chunkSize=job.chunk_size,
        chunkOverlap=job.chunk_overlap,
        stats=job.stats_json or {},
        errorMessage=job.error_message,
        queueJobId=job.queue_job_id,
        createdAt=job.created_at,
        startedAt=job.started_at,
        finishedAt=job.finished_at,
    )
