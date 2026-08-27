"""Prometheus OpenMetrics and structured JSON Telemetry endpoints."""

from fastapi import APIRouter, status
from fastapi.responses import PlainTextResponse, JSONResponse

from ...core.telemetry import telemetry
from ...persistence.database import engine
from ...orchestration.background_manager import get_background_manager

telemetry_router = APIRouter(tags=["Telemetry"])


def _update_dynamic_gauges() -> None:
    """Collects current in-process gauges from DB pool and background manager without executing DB queries."""
    # 1. Database Pool Stats
    try:
        pool = engine.pool
        checked_out = getattr(pool, "checkedout", lambda: 0)()
        size = getattr(pool, "size", lambda: 5)()
        overflow = getattr(pool, "overflow", lambda: 0)()
        telemetry.set_gauge("database_connections_checked_out", float(checked_out))
        telemetry.set_gauge("database_pool_size", float(size))
        telemetry.set_gauge("database_pool_overflow", float(overflow))
    except Exception:
        pass

    # 2. Background Execution Manager Stats
    try:
        bg_mgr = get_background_manager()
        active_count = len(bg_mgr._active_tasks)
        telemetry.set_gauge("background_active_executions", float(active_count))
    except Exception:
        pass


@telemetry_router.get(
    "/metrics",
    summary="Prometheus / OpenMetrics Metrics Exposition",
    response_class=PlainTextResponse,
)
async def get_prometheus_metrics() -> PlainTextResponse:
    """
    Exposes process-local application metrics in standard Prometheus/OpenMetrics text format.
    Low-cardinality, lightweight, and suitable for scraping by Prometheus or cloud monitoring agents.
    """
    _update_dynamic_gauges()
    prom_text = telemetry.to_prometheus_text()
    return PlainTextResponse(
        content=prom_text,
        status_code=status.HTTP_200_OK,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@telemetry_router.get(
    "/telemetry",
    summary="Structured JSON Telemetry Snapshot",
    response_class=JSONResponse,
)
async def get_telemetry_snapshot() -> JSONResponse:
    """
    Returns a comprehensive JSON snapshot of all process-local metrics,
    including counters, gauges, histograms, database pool health, and worker telemetry.
    """
    _update_dynamic_gauges()
    snapshot = telemetry.to_dict()
    return JSONResponse(
        content=snapshot,
        status_code=status.HTTP_200_OK,
    )
