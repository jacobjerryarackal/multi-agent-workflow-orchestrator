"""Application runtime settings and environment variable configuration."""

from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/orchestrator_db"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
