from __future__ import annotations

import logging
import time
from functools import lru_cache

from fastapi import Depends, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .auth import create_auth_token, get_current_user_id, require_admin_token
from .config import get_settings
from .database import get_db
from .embeddings import EmbeddingClient
from .errors import ApiHttpError
from .feedback import list_wrong_questions, save_question_feedback
from .history import (
    get_learning_record,
    list_learning_records,
    save_learning_record,
    to_detail,
    upsert_wechat_user,
)
from .llm import LangChainAiClient
from .observability import (
    REQUEST_ID_HEADER,
    configure_logging,
    log_event,
    new_request_id,
    reset_request_id,
    set_request_id,
)
from .rate_limit import enforce_generation_rate_limit
from .rag_admin import (
    get_admin_chunk,
    get_admin_question,
    list_admin_chunks,
    list_admin_collections,
    list_admin_documents,
    list_admin_questions,
    reembed_admin_chunk,
    reembed_admin_question,
    update_admin_chunk,
    update_admin_collection,
    update_admin_document,
    update_admin_question,
)
from .schemas import (
    AiGenerationError,
    ApiError,
    AuthResponse,
    GenerateQuizRequest,
    GenerateQuizResponse,
    GenerateReportRequest,
    GenerateReportResponse,
    HistoryListResponse,
    HistoryRecordDetail,
    HistorySaveRequest,
    HistorySaveResponse,
    QuestionFeedbackRequest,
    QuestionFeedbackResponse,
    RagAdminChunkItem,
    RagAdminChunkListResponse,
    RagAdminChunkUpdateRequest,
    RagAdminCollectionItem,
    RagAdminCollectionListResponse,
    RagAdminCollectionUpdateRequest,
    RagAdminDocumentItem,
    RagAdminDocumentListResponse,
    RagAdminDocumentUpdateRequest,
    RagAdminQuestionItem,
    RagAdminQuestionListResponse,
    RagAdminQuestionUpdateRequest,
    RagAdminReembedResponse,
    WechatLoginRequest,
    WrongQuestionListResponse,
)
from .services import AiServiceError, LearningService
from .wechat import exchange_wechat_code


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="Brain Rush API", version="0.1.0")
    settings = get_settings()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_observability_middleware(request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or new_request_id()
        request.state.request_id = request_id
        token = set_request_id(request_id)
        started_at = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            log_event(
                "http_request_failed",
                level=logging.ERROR,
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
                error_type=type(exc).__name__,
                exc_info=True,
            )
            reset_request_id(token)
            raise

        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        response.headers[REQUEST_ID_HEADER] = request_id
        log_event(
            "http_request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        reset_request_id(token)
        return response

    @app.exception_handler(ApiHttpError)
    async def handle_api_http_error(request: Request, exc: ApiHttpError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        log_event(
            "api_error",
            request_id=request_id,
            status_code=exc.status_code,
            code=exc.code,
            detail=exc.detail,
        )
        payload = ApiError(code=exc.code, detail=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=payload.model_dump(),
            headers={REQUEST_ID_HEADER: request_id} if request_id else None,
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/api/auth/wechat",
        response_model=AuthResponse,
        responses={401: {"model": ApiError}, 500: {"model": ApiError}, 502: {"model": ApiError}},
    )
    async def auth_wechat(
        payload: WechatLoginRequest,
        db: Session = Depends(get_db),
    ) -> AuthResponse:
        wechat_session = await exchange_wechat_code(payload.code, settings)
        user = upsert_wechat_user(db, wechat_session.openid, wechat_session.unionid)
        return AuthResponse(token=create_auth_token(user.id, settings), userId=user.id)

    @app.post(
        "/api/generate-quiz",
        response_model=GenerateQuizResponse,
        responses={502: {"model": AiGenerationError}},
    )
    async def generate_quiz(
        payload: GenerateQuizRequest,
        _: None = Depends(enforce_generation_rate_limit),
        service: LearningService = Depends(get_learning_service),
    ) -> GenerateQuizResponse:
        try:
            return service.generate_quiz(payload.inputText)
        except AiServiceError as exc:
            raise ApiHttpError(status_code=502, code=exc.code, detail=exc.detail) from exc

    @app.post(
        "/api/generate-report",
        response_model=GenerateReportResponse,
        responses={502: {"model": AiGenerationError}},
    )
    async def generate_report(
        payload: GenerateReportRequest,
        _: None = Depends(enforce_generation_rate_limit),
        service: LearningService = Depends(get_learning_service),
    ) -> GenerateReportResponse:
        try:
            return service.generate_report(payload)
        except AiServiceError as exc:
            raise ApiHttpError(status_code=502, code=exc.code, detail=exc.detail) from exc

    @app.post(
        "/api/history",
        response_model=HistorySaveResponse,
        responses={401: {"model": ApiError}, 404: {"model": ApiError}},
    )
    async def create_history_record(
        payload: HistorySaveRequest,
        user_id: str = Depends(get_current_user_id),
        db: Session = Depends(get_db),
    ) -> HistorySaveResponse:
        record = save_learning_record(db, user_id, payload)
        return HistorySaveResponse(record=to_detail(record))

    @app.get(
        "/api/history",
        response_model=HistoryListResponse,
        responses={401: {"model": ApiError}},
    )
    async def get_history_records(
        user_id: str = Depends(get_current_user_id),
        db: Session = Depends(get_db),
    ) -> HistoryListResponse:
        return HistoryListResponse(records=list_learning_records(db, user_id))

    @app.get(
        "/api/history/{record_id}",
        response_model=HistoryRecordDetail,
        responses={401: {"model": ApiError}, 404: {"model": ApiError}},
    )
    async def get_history_record(
        record_id: str,
        user_id: str = Depends(get_current_user_id),
        db: Session = Depends(get_db),
    ) -> HistoryRecordDetail:
        return get_learning_record(db, user_id, record_id)

    @app.post(
        "/api/question-feedback",
        response_model=QuestionFeedbackResponse,
        responses={401: {"model": ApiError}},
    )
    async def create_question_feedback(
        payload: QuestionFeedbackRequest,
        user_id: str = Depends(get_current_user_id),
        db: Session = Depends(get_db),
    ) -> QuestionFeedbackResponse:
        return save_question_feedback(db, user_id, payload)

    @app.get(
        "/api/wrong-questions",
        response_model=WrongQuestionListResponse,
        responses={401: {"model": ApiError}},
    )
    async def get_wrong_questions(
        user_id: str = Depends(get_current_user_id),
        db: Session = Depends(get_db),
    ) -> WrongQuestionListResponse:
        return WrongQuestionListResponse(items=list_wrong_questions(db, user_id))

    @app.get(
        "/api/admin/rag/collections",
        response_model=RagAdminCollectionListResponse,
        responses={401: {"model": ApiError}, 404: {"model": ApiError}},
    )
    async def admin_list_collections(
        _: None = Depends(require_admin_token),
        db: Session = Depends(get_db),
    ) -> RagAdminCollectionListResponse:
        return list_admin_collections(db)

    @app.patch(
        "/api/admin/rag/collections/{collection_id}",
        response_model=RagAdminCollectionItem,
        responses={401: {"model": ApiError}, 404: {"model": ApiError}},
    )
    async def admin_update_collection(
        collection_id: str,
        payload: RagAdminCollectionUpdateRequest,
        _: None = Depends(require_admin_token),
        db: Session = Depends(get_db),
    ) -> RagAdminCollectionItem:
        return update_admin_collection(db, collection_id, payload)

    @app.get(
        "/api/admin/rag/documents",
        response_model=RagAdminDocumentListResponse,
        responses={401: {"model": ApiError}, 404: {"model": ApiError}},
    )
    async def admin_list_documents(
        collection_id: str | None = Query(default=None, alias="collectionId"),
        q: str | None = None,
        status: str | None = None,
        is_active: bool | None = Query(default=None, alias="isActive"),
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        _: None = Depends(require_admin_token),
        db: Session = Depends(get_db),
    ) -> RagAdminDocumentListResponse:
        return list_admin_documents(
            db,
            collection_id=collection_id,
            q=q,
            status=status,
            is_active=is_active,
            limit=limit,
            offset=offset,
        )

    @app.patch(
        "/api/admin/rag/documents/{document_id}",
        response_model=RagAdminDocumentItem,
        responses={401: {"model": ApiError}, 404: {"model": ApiError}},
    )
    async def admin_update_document(
        document_id: str,
        payload: RagAdminDocumentUpdateRequest,
        _: None = Depends(require_admin_token),
        db: Session = Depends(get_db),
    ) -> RagAdminDocumentItem:
        return update_admin_document(db, document_id, payload)

    @app.get(
        "/api/admin/rag/chunks",
        response_model=RagAdminChunkListResponse,
        responses={401: {"model": ApiError}, 404: {"model": ApiError}},
    )
    async def admin_list_chunks(
        collection_id: str | None = Query(default=None, alias="collectionId"),
        document_id: str | None = Query(default=None, alias="documentId"),
        q: str | None = None,
        is_active: bool | None = Query(default=None, alias="isActive"),
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        _: None = Depends(require_admin_token),
        db: Session = Depends(get_db),
    ) -> RagAdminChunkListResponse:
        return list_admin_chunks(
            db,
            collection_id=collection_id,
            document_id=document_id,
            q=q,
            is_active=is_active,
            limit=limit,
            offset=offset,
        )

    @app.get(
        "/api/admin/rag/chunks/{chunk_id}",
        response_model=RagAdminChunkItem,
        responses={401: {"model": ApiError}, 404: {"model": ApiError}},
    )
    async def admin_get_chunk(
        chunk_id: str,
        _: None = Depends(require_admin_token),
        db: Session = Depends(get_db),
    ) -> RagAdminChunkItem:
        return get_admin_chunk(db, chunk_id)

    @app.patch(
        "/api/admin/rag/chunks/{chunk_id}",
        response_model=RagAdminChunkItem,
        responses={401: {"model": ApiError}, 404: {"model": ApiError}},
    )
    async def admin_update_chunk(
        chunk_id: str,
        payload: RagAdminChunkUpdateRequest,
        _: None = Depends(require_admin_token),
        db: Session = Depends(get_db),
    ) -> RagAdminChunkItem:
        return update_admin_chunk(db, chunk_id, payload)

    @app.post(
        "/api/admin/rag/chunks/{chunk_id}/reembed",
        response_model=RagAdminReembedResponse,
        responses={400: {"model": ApiError}, 401: {"model": ApiError}, 404: {"model": ApiError}},
    )
    async def admin_reembed_chunk(
        chunk_id: str,
        _: None = Depends(require_admin_token),
        db: Session = Depends(get_db),
        embedding_client: EmbeddingClient = Depends(get_admin_embedding_client),
    ) -> RagAdminReembedResponse:
        return reembed_admin_chunk(db, chunk_id, embedding_client)

    @app.get(
        "/api/admin/rag/questions",
        response_model=RagAdminQuestionListResponse,
        responses={401: {"model": ApiError}, 404: {"model": ApiError}},
    )
    async def admin_list_questions(
        collection_id: str | None = Query(default=None, alias="collectionId"),
        q: str | None = None,
        is_active: bool | None = Query(default=None, alias="isActive"),
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        _: None = Depends(require_admin_token),
        db: Session = Depends(get_db),
    ) -> RagAdminQuestionListResponse:
        return list_admin_questions(
            db,
            collection_id=collection_id,
            q=q,
            is_active=is_active,
            limit=limit,
            offset=offset,
        )

    @app.get(
        "/api/admin/rag/questions/{question_id}",
        response_model=RagAdminQuestionItem,
        responses={401: {"model": ApiError}, 404: {"model": ApiError}},
    )
    async def admin_get_question(
        question_id: str,
        _: None = Depends(require_admin_token),
        db: Session = Depends(get_db),
    ) -> RagAdminQuestionItem:
        return get_admin_question(db, question_id)

    @app.patch(
        "/api/admin/rag/questions/{question_id}",
        response_model=RagAdminQuestionItem,
        responses={401: {"model": ApiError}, 404: {"model": ApiError}},
    )
    async def admin_update_question(
        question_id: str,
        payload: RagAdminQuestionUpdateRequest,
        _: None = Depends(require_admin_token),
        db: Session = Depends(get_db),
    ) -> RagAdminQuestionItem:
        return update_admin_question(db, question_id, payload)

    @app.post(
        "/api/admin/rag/questions/{question_id}/reembed",
        response_model=RagAdminReembedResponse,
        responses={400: {"model": ApiError}, 401: {"model": ApiError}, 404: {"model": ApiError}},
    )
    async def admin_reembed_question(
        question_id: str,
        _: None = Depends(require_admin_token),
        db: Session = Depends(get_db),
        embedding_client: EmbeddingClient = Depends(get_admin_embedding_client),
    ) -> RagAdminReembedResponse:
        return reembed_admin_question(db, question_id, embedding_client)

    return app


@lru_cache
def get_ai_client() -> LangChainAiClient:
    try:
        return LangChainAiClient(get_settings())
    except RuntimeError as exc:
        raise ApiHttpError(status_code=502, code="ai_auth_error", detail=str(exc)) from exc


def get_admin_embedding_client() -> EmbeddingClient:
    return EmbeddingClient(get_settings())


def get_learning_service(
    ai_client: LangChainAiClient = Depends(get_ai_client),
    db: Session = Depends(get_db),
) -> LearningService:
    return LearningService(ai_client=ai_client, db=db)


app = create_app()
