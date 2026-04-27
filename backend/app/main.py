from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .llm import LangChainAiClient
from .schemas import (
    AiGenerationError,
    GenerateQuizRequest,
    GenerateQuizResponse,
    GenerateReportRequest,
    GenerateReportResponse,
)
from .services import AiServiceError, LearningService


class AiHttpError(RuntimeError):
    def __init__(self, status_code: int, code: str, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.detail = detail


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

    @app.exception_handler(AiHttpError)
    async def handle_ai_http_error(_: Request, exc: AiHttpError) -> JSONResponse:
        payload = AiGenerationError(code=exc.code, detail=exc.detail)
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

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
            raise AiHttpError(status_code=502, code=exc.code, detail=exc.detail) from exc

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
            raise AiHttpError(status_code=502, code=exc.code, detail=exc.detail) from exc

    return app


@lru_cache
def get_ai_client() -> LangChainAiClient:
    try:
        return LangChainAiClient(get_settings())
    except RuntimeError as exc:
        raise AiHttpError(status_code=502, code="ai_auth_error", detail=str(exc)) from exc


def get_learning_service(
    ai_client: LangChainAiClient = Depends(get_ai_client),
) -> LearningService:
    return LearningService(ai_client=ai_client)


app = create_app()
