"""FastAPI application factory, lifecycle management, and ASGI entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .core.config import Settings, settings
from .api.errors import register_exception_handlers
from .api.middleware.correlation import CorrelationIdMiddleware, get_correlation_id
from .api.middleware.security import SecurityHeadersMiddleware
from .api.v1 import v1_router
from .persistence.database import engine, Base
from .persistence.models import (
    WorkflowModel,
    WorkflowTaskModel,
    WorkflowExecutionModel,
    TaskExecutionModel,
    WorkflowEventModel,
    ArtifactModel,
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager:
    - Startup: Confirms configuration, runs startup execution recovery, starts watchdog supervisor.
    - Shutdown: Performs graceful shutdown of background tasks and disposes database connection pool.
    """
    logger.info(
        "Starting Multi-Agent Workflow Orchestrator API",
        app_name=settings.APP_NAME,
        env=settings.APP_ENV,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Startup recovery & watchdog supervisor
    from .orchestration.background_manager import get_background_manager
    bg_manager = get_background_manager()
    bg_manager._shutdown_event.clear()
    await bg_manager.recover_stranded_executions()
    bg_manager.start_watchdog(interval_seconds=10.0)

    yield

    logger.info("Shutting down Multi-Agent Workflow Orchestrator API")
    await bg_manager.graceful_shutdown(timeout_seconds=5.0)
    bg_manager._shutdown_event.clear()



def create_app(custom_settings: Optional[Settings] = None) -> FastAPI:
    """
    Application factory creating and configuring a FastAPI instance.
    Configures metadata, lifespan, security headers, correlation IDs, CORS,
    centralized error handlers, and core API routers.
    """
    active_settings = custom_settings or settings

    app = FastAPI(
        title="Multi-Agent Workflow Orchestrator API",
        description="Production-grade API for declarative multi-agent workflow orchestration, evaluation, and recovery.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # 1. Register Custom Middlewares (Lifo execution order in Starlette)
    # Security headers applied on top
    app.add_middleware(SecurityHeadersMiddleware)

    # Correlation ID middleware
    app.add_middleware(CorrelationIdMiddleware)

    # CORS Middleware configured from environment
    app.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID"],
    )

    # 2. Register Centralized Exception Handlers
    register_exception_handlers(app)

    # 3. Register Core API Routers
    app.include_router(v1_router)

    # 4. Root Service Metadata Route
    @app.get("/", tags=["Root"], summary="API Root Metadata")
    async def root_info() -> JSONResponse:
        return JSONResponse(
            status_code=200,
            content={
                "name": active_settings.APP_NAME,
                "version": "1.0.0",
                "docs_url": "/docs",
                "health_url": "/api/v1/health",
                "correlation_id": get_correlation_id(),
            },
        )

    return app


# Default ASGI application instance
app = create_app()
