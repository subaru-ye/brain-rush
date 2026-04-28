from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .auth import create_auth_token, get_current_user_id
from .config import get_settings
from .database import get_db
from .errors import ApiHttpError
from .history import (
    get_learning_record,
    list_learning_records,
    save_learning_record,
    to_detail,
    upsert_wechat_user,
)
from .llm import LangChainAiClient
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
    WechatLoginRequest,
)
from .services import AiServiceError, LearningService
from .wechat import exchange_wechat_code


def create_app() -> FastAPI:
    app = FastAPI(title="Brain Rush API", version="0.1.0")
    settings = get_settings()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ApiHttpError)
    async def handle_api_http_error(_: Request, exc: ApiHttpError) -> JSONResponse:
        payload = ApiError(code=exc.code, detail=exc.detail)
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

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

    return app


@lru_cache
def get_ai_client() -> LangChainAiClient:
    try:
        return LangChainAiClient(get_settings())
    except RuntimeError as exc:
        raise ApiHttpError(status_code=502, code="ai_auth_error", detail=str(exc)) from exc


def get_learning_service(
    ai_client: LangChainAiClient = Depends(get_ai_client),
) -> LearningService:
    return LearningService(ai_client=ai_client)


app = create_app()
