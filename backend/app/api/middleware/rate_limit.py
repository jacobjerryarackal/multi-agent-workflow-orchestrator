"""Process-local, in-memory rate limiting middleware for DDoS and abuse mitigation."""

from collections import defaultdict
from datetime import datetime, timezone
import threading
import time
from typing import Dict, List, Optional
import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .correlation import get_correlation_id

logger = structlog.get_logger(__name__)


class ProcessLocalRateLimiter(BaseHTTPMiddleware):
    """
    In-process, sliding-window rate limiting middleware.
    
    ARCHITECTURAL LIMITATION & FREE-TIER DESIGN:
    1. State is strictly process-local (in-memory per Python process/worker).
    2. Does NOT share quota across multiple Uvicorn workers or multiple container replicas
       without an external distributed store (e.g., Redis).
    3. Provides immediate, zero-infrastructure abuse protection for free-tier single-worker deployments
       and per-worker bounding in multi-worker environments.
    """

    def __init__(
        self,
        app,
        requests_per_minute: int = 120,
        burst_allowance: int = 30,
        enabled: bool = True,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window_seconds = 60.0
        self.burst_allowance = burst_allowance
        self.enabled = enabled
        self._ip_history: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def _get_client_ip(self, request: Request) -> str:
        # Check standard reverse proxy headers (Render / Cloudflare / Vercel forwarders)
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        if request.client:
            return request.client.host
        return "127.0.0.1"

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not self.enabled:
            return await call_next(request)

        # Exclude health check and metrics endpoints from rate limits to prevent probe failures
        path = request.url.path
        if path in ("/health", "/api/v1/health", "/api/v1/metrics", "/api/v1/telemetry", "/docs", "/redoc", "/openapi.json"):
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        now = time.time()
        correlation_id = get_correlation_id()

        with self._lock:
            history = self._ip_history[client_ip]
            # Prune timestamps older than window
            cutoff = now - self.window_seconds
            self._ip_history[client_ip] = [t for t in history if t > cutoff]
            current_count = len(self._ip_history[client_ip])

            if current_count >= (self.requests_per_minute + self.burst_allowance):
                logger.warning(
                    "Process-local rate limit exceeded",
                    client_ip=client_ip,
                    requests_in_window=current_count,
                    limit=self.requests_per_minute,
                    correlation_id=correlation_id,
                )
                return self._create_429_response(correlation_id)

            self._ip_history[client_ip].append(now)

        response = await call_next(request)
        return response

    def _create_429_response(self, correlation_id: str) -> JSONResponse:
        error_payload = {
            "error": {
                "code": "TOO_MANY_REQUESTS",
                "message": "Rate limit exceeded. Please retry after some time.",
                "correlation_id": correlation_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        }
        headers = {
            "X-Correlation-ID": correlation_id,
            "X-Content-Type-Options": "nosniff",
            "Retry-After": "60",
        }
        return JSONResponse(status_code=429, content=error_payload, headers=headers)
