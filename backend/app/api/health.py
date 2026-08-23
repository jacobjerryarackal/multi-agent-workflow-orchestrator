"""System health and readiness check endpoint."""

from datetime import datetime, timezone
from typing import Any, Dict, List
import structlog
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from .dependencies import get_db_session, get_agent_registry
from .middleware.correlation import get_correlation_id

logger = structlog.get_logger(__name__)
health_router = APIRouter(tags=["Health"])


class HealthComponentStatus(BaseModel):
    status: str
    details: Dict[str, Any] = {}


class HealthResponse(BaseModel):
    status: str  # healthy, degraded, unavailable
    app_name: str
    app_env: str
    correlation_id: str
    timestamp: str
    components: Dict[str, HealthComponentStatus]


@health_router.get(
    "/health",
    response_model=HealthResponse,
    summary="System Health & Readiness Check",
)
async def check_system_health(
    session: AsyncSession = Depends(get_db_session),
    registry=Depends(get_agent_registry),
) -> JSONResponse:
    """
    Evaluates real system readiness:
    - PostgreSQL connectivity (via ping query)
    - Agent registry registration
    - Model provider configuration
    """
    correlation_id = get_correlation_id()
    now_iso = datetime.now(timezone.utc).isoformat()
    components: Dict[str, HealthComponentStatus] = {}

    overall_status = "healthy"
    status_code = status.HTTP_200_OK

    # 1. Database Connectivity Check
    try:
        await session.execute(text("SELECT 1"))
        components["database"] = HealthComponentStatus(
            status="healthy",
            details={"engine": "PostgreSQL 16", "pool": "asyncpg"},
        )
    except Exception as exc:
        logger.error("Database health check failed", error=str(exc), correlation_id=correlation_id)
        components["database"] = HealthComponentStatus(
            status="unavailable",
            details={"error": "Database connection failed"},
        )
        overall_status = "unavailable"
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    # 2. Agent Registry Check
    try:
        registered_agents: List[str] = [agent.agent_id for agent in registry.list_agents()]
        expected_builtins = ["planner", "researcher", "analyst", "reviewer", "synthesizer"]
        all_present = all(agent_id in registered_agents for agent_id in expected_builtins)

        components["agent_registry"] = HealthComponentStatus(
            status="healthy" if all_present else "degraded",
            details={
                "registered_count": len(registered_agents),
                "agents": registered_agents,
            },
        )
        if not all_present and overall_status != "unavailable":
            overall_status = "degraded"
    except Exception as exc:
        logger.error("Agent registry health check failed", error=str(exc), correlation_id=correlation_id)
        components["agent_registry"] = HealthComponentStatus(
            status="unavailable",
            details={"error": "Registry query failed"},
        )
        overall_status = "unavailable"
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    # 3. Model Provider Status
    gemini_key_configured = bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip())
    components["model_provider"] = HealthComponentStatus(
        status="healthy" if gemini_key_configured else "degraded",
        details={
            "provider": "Google Gemini",
            "api_key_configured": gemini_key_configured,
            "default_model": settings.DEFAULT_MODEL_NAME,
        },
    )
    if not gemini_key_configured and overall_status == "healthy":
        overall_status = "degraded"

    payload = HealthResponse(
        status=overall_status,
        app_name=settings.APP_NAME,
        app_env=settings.APP_ENV,
        correlation_id=correlation_id,
        timestamp=now_iso,
        components=components,
    )

    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(),
    )
