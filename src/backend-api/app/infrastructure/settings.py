from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Application
    APP_ENV: str = "dev"
    PRODUCT_NAME: str = "MyProduct"
    SECRET_KEY: str = "change-me-in-production"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://app:app@db:5432/app"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    # MinIO (S3-compatible)
    S3_ENDPOINT_URL: str = "http://minio:9000"
    S3_ACCESS_KEY: str = "minio"
    S3_SECRET_KEY: str = "miniominio"
    S3_BUCKET: str = "app-storage"
    S3_REGION: str = "us-east-1"

    # JWT
    JWT_PRIVATE_KEY_PATH: str = ""
    JWT_PUBLIC_KEY_PATH: str = ""
    JWT_ALGORITHM: str = "RS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Rate Limiting
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15

    # SMTP
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@example.com"

    # Frontend URL (for password reset links)
    FRONTEND_URL: str = "http://localhost:4200"

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    # Logging
    LOG_LEVEL: str = "INFO"

    # FIPE Provider
    FIPE_PROVIDER: str = "brasilapi"  # brasilapi | mock

    # LLM Provider
    LLM_PROVIDER: str = "openai"  # openai | anthropic | groq | gemini | ollama
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o"

    # WhatsApp Provider
    WHATSAPP_PROVIDER: str = ""  # zapi | uazapi | evolution_api

    # Agent
    AGENT_DRY_RUN: bool = False

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> "Settings":
        if self.APP_ENV != "dev":
            if self.SECRET_KEY == "change-me-in-production":
                raise ValueError("SECRET_KEY must be set in non-dev environments")
            if self.S3_ACCESS_KEY == "minio" or self.S3_SECRET_KEY == "miniominio":
                raise ValueError("S3 credentials must be set in non-dev environments")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
