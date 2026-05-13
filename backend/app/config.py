from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    app_env: str = Field(default="development", alias="APP_ENV")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.deepseek.com", alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="deepseek-v4-flash", alias="OPENAI_MODEL")
    openai_timeout_seconds: float = Field(default=60.0, alias="OPENAI_TIMEOUT_SECONDS")
    openai_max_retries: int = Field(default=2, alias="OPENAI_MAX_RETRIES")
    embedding_api_key: str = Field(default="", alias="EMBEDDING_API_KEY")
    embedding_base_url: str = Field(default="", alias="EMBEDDING_BASE_URL")
    embedding_model: str = Field(default="", alias="EMBEDDING_MODEL")
    embedding_dimensions: int = Field(default=1536, alias="EMBEDDING_DIMENSIONS")
    embedding_timeout_seconds: float = Field(default=30.0, alias="EMBEDDING_TIMEOUT_SECONDS")
    embedding_max_retries: int = Field(default=2, alias="EMBEDDING_MAX_RETRIES")
    generation_rate_limit_max_requests: int = Field(
        default=10,
        alias="GENERATION_RATE_LIMIT_MAX_REQUESTS",
    )
    generation_rate_limit_window_seconds: int = Field(
        default=3600,
        alias="GENERATION_RATE_LIMIT_WINDOW_SECONDS",
    )
    frontend_origins: str = Field(default="*", alias="FRONTEND_ORIGINS")
    database_url: str = Field(
        default="postgresql+psycopg://brain_rush:brain_rush@localhost:5432/brain_rush",
        alias="DATABASE_URL",
    )
    auth_token_secret: str = Field(
        default="dev-brain-rush-secret-change-me-32-bytes",
        alias="AUTH_TOKEN_SECRET",
    )
    auth_token_expire_days: int = Field(default=30, alias="AUTH_TOKEN_EXPIRE_DAYS")
    admin_api_token: str = Field(default="", alias="ADMIN_API_TOKEN")
    wechat_appid: str = Field(default="", alias="WECHAT_APPID")
    wechat_secret: str = Field(default="", alias="WECHAT_SECRET")

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        if self.frontend_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]

    @property
    def resolved_embedding_api_key(self) -> str:
        return self.embedding_api_key or self.openai_api_key

    @property
    def resolved_embedding_base_url(self) -> str:
        return self.embedding_base_url or self.openai_base_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
