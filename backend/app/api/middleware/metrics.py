"""HTTP Request metrics middleware and route normalization."""

import re
import time
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from ...core.telemetry import telemetry

# Regex rules for normalizing paths to low-cardinality route templates
_NORMALIZE_RULES = [
    (re.compile(r"^/api/v1/workflows/[^/]+/executions/?$"), "/api/v1/workflows/{workflow_id}/executions"),
    (re.compile(r"^/api/v1/workflows/[^/]+/?$"), "/api/v1/workflows/{workflow_id}"),
    (re.compile(r"^/api/v1/executions/[^/]+/artifacts/[^/]+/?$"), "/api/v1/executions/{execution_id}/artifacts/{artifact_id}"),
    (re.compile(r"^/api/v1/executions/[^/]+/artifacts/?$"), "/api/v1/executions/{execution_id}/artifacts"),
    (re.compile(r"^/api/v1/executions/[^/]+/events/?$"), "/api/v1/executions/{execution_id}/events"),
    (re.compile(r"^/api/v1/executions/[^/]+/tasks/[^/]+/approval/?$"), "/api/v1/executions/{execution_id}/tasks/{task_key}/approval"),
    (re.compile(r"^/api/v1/executions/[^/]+/cancel/?$"), "/api/v1/executions/{execution_id}/cancel"),
    (re.compile(r"^/api/v1/executions/[^/]+/?$"), "/api/v1/executions/{execution_id}"),
    (re.compile(r"^/api/v1/agents/[^/]+/?$"), "/api/v1/agents/{agent_id}"),
]


def normalize_route_path(path: str, request: Request) -> str:
    """
    Derives normalized route pattern from FastAPI route if available,
    falling back to strict regex template substitution to prevent label cardinality explosion.
    """
    # 1. Check if starlette router already resolved the route pattern
    route = request.scope.get("route")
    if route and hasattr(route, "path"):
        return route.path

    # 2. Match against known route normalization rules
    path_stripped = path.rstrip("/") or "/"
    for pattern, template in _NORMALIZE_RULES:
        if pattern.match(path):
            return template

    # 3. Known static endpoints
    if path in (
        "/",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/v1/health",
        "/api/v1/metrics",
        "/api/v1/telemetry",
        "/api/v1/workflows",
        "/api/v1/executions",
        "/api/v1/agents",
    ):
        return path_stripped

    # 4. If unrecognized nested path, sanitize potential UUIDs or numeric IDs
    sanitized = re.sub(r"/[0-9a-fA-F-]{8,}/?", "/{id}", path_stripped)
    return sanitized


class HttpMetricsMiddleware(BaseHTTPMiddleware):
    """
    Captures HTTP request counts, durations, status codes, and error totals.
    Uses normalized low-cardinality route labels.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        method = request.method
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            duration = time.perf_counter() - start_time
            status_code = str(response.status_code)
            route = normalize_route_path(request.url.path, request)

            labels = {
                "method": method,
                "route": route,
                "status_code": status_code,
            }

            telemetry.increment_counter("http_requests_total", value=1.0, labels=labels)
            telemetry.observe_histogram(
                "http_request_duration_seconds",
                value=duration,
                labels={"method": method, "route": route},
            )

            if response.status_code >= 400:
                telemetry.increment_counter(
                    "http_errors_total",
                    value=1.0,
                    labels={
                        "method": method,
                        "route": route,
                        "status_code": status_code,
                        "error_type": "client_error" if response.status_code < 500 else "server_error",
                    },
                )

            return response
        except Exception as exc:
            duration = time.perf_counter() - start_time
            route = normalize_route_path(request.url.path, request)
            telemetry.increment_counter(
                "http_requests_total",
                value=1.0,
                labels={"method": method, "route": route, "status_code": "500"},
            )
            telemetry.observe_histogram(
                "http_request_duration_seconds",
                value=duration,
                labels={"method": method, "route": route},
            )
            telemetry.increment_counter(
                "http_errors_total",
                value=1.0,
                labels={
                    "method": method,
                    "route": route,
                    "status_code": "500",
                    "error_type": "unhandled_exception",
                },
            )
            raise
