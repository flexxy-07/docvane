from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # General App Config
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"
    DEBUG: bool = True
    PROJECT_NAME: str = "Docvane"
    API_V1_STR: str = "/api/v1"

    # PostgreSQL + pgvector (local Docker port 5433)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/docvane"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # Redis (local Docker port 6379)
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # Object Storage (Cloudflare R2 / S3)
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY_ID: str = "mock-key"
    S3_SECRET_ACCESS_KEY: str = "mock-secret"
    S3_BUCKET_NAME: str = "docvane-documents"
    S3_REGION: str = "auto"

    # LLM Settings
    GEMINI_API_KEY: str = ""
    DEFAULT_LLM_MODEL: str = "gemini/gemini-1.5-flash"
    EMBEDDING_MODEL: str = "text-embedding-004"
    EMBEDDING_DIM: int = 768
    RERANKER_MODEL: str = "BAAI/bge-reranker-base"

    # Observability
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
