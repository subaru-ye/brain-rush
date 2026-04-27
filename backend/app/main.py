from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings, get_settings
from .llm import LangChainAiClient
from .schemas import (
    AiGenerationError,
    GenerateQuizRequest,
    GenerateQuizResponse,
    GenerateReportRequest,
    GenerateReportResponse,
)
from .services import AiServiceError, LearningService


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
            raise HTTPException(status_code=502, detail=str(exc)) from exc

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
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return app


def get_learning_service(settings: Settings = Depends(get_settings)) -> LearningService:
    try:
        return LearningService(ai_client=LangChainAiClient(settings))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


app = create_app()
