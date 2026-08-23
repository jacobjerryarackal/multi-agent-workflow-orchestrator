"""API v1 Router aggregation."""

from fastapi import APIRouter

from .workflows import workflows_router
from .executions import executions_router
from .events import events_router
from .artifacts import artifacts_router
from .agents import agents_router
from ..health import health_router

v1_router = APIRouter(prefix="/api/v1")

v1_router.include_router(health_router)
v1_router.include_router(workflows_router)
v1_router.include_router(executions_router)
v1_router.include_router(events_router)
v1_router.include_router(artifacts_router)
v1_router.include_router(agents_router)

__all__ = ["v1_router"]
