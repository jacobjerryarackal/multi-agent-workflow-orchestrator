"""Application runtime settings and environment variable configuration."""

from typing import List, Any
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(url: str) -> str:
    """
    Normalizes database connection URLs for SQLAlchemy AsyncEngine.
    - Converts postgres:// or postgresql:// to postgresql+asyncpg://
    - Preserves postgresql+asyncpg:// and sqlite+aiosqlite://
    - Converts sqlite:// to sqlite+aiosqlite:// if not already async
    """
    if not url:
        return url

    url = url.strip()
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://"):]
    elif url.startswith("sqlite://") and not url.startswith("sqlite+aiosqlite://"):
        return "sqlite+aiosqlite://" + url[len("sqlite://"):]
    return url


class Settings(BaseSettings):
    # Application Configuration
    APP_NAME: str = "MultiAgentWorkflowOrchestrator"
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = True

    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Database Configuration (PostgreSQL)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:12345678@localhost:5432/orchestrator_test_db"
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 5
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 1800
    DATABASE_POOL_PRE_PING: bool = True

    # Google Gemini API Provider
    GEMINI_API_KEY: str = Field(default="", description="Google Gemini API key")
    DEFAULT_MODEL_NAME: str = "gemini-2.5-flash"
    REASONING_MODEL_NAME: str = "gemini-2.5-pro"

    # Orchestration Limits & Invariants
    MAX_WORKFLOW_DURATION_SECONDS: int = 600
    MAX_TASK_DURATION_SECONDS: int = 60
    MAX_PARALLEL_TASKS: int = 5
    MAX_TASK_RETRIES: int = 3
    MAX_TOTAL_WORKFLOW_STEPS: int = 50
    MAX_OUTPUT_SIZE_BYTES: int = 1_048_576  # 1 MB
    MAX_REQUEST_SIZE_BYTES: int = 10_485_760  # 10 MB

    # Rate Limiting Configuration (Process-local)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 120
    RATE_LIMIT_BURST: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def validate_database_url(cls, v: Any) -> str:
        if isinstance(v, str):
            return normalize_database_url(v)
        return str(v)

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
