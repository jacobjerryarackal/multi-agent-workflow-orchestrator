"""Production request body size limiting middleware."""

from datetime import datetime, timezone
import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .correlation import get_correlation_id

logger = structlog.get_logger(__name__)

# Default maximum allowed request body size: 10 MB (10 * 1024 * 1024 bytes)
DEFAULT_MAX_REQUEST_SIZE_BYTES = 10 * 1024 * 1024


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Defensively limits incoming HTTP request body sizes to prevent memory exhaustion / DoS attacks.
    Enforces a strict 10 MB cap by default, returning a standardized 413 Payload Too Large error.
    """

    def __init__(self, app, max_size_bytes: int = DEFAULT_MAX_REQUEST_SIZE_BYTES):
        super().__init__(app)
        self.max_size_bytes = max_size_bytes

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = get_correlation_id()

        # 1. Fast path: Check Content-Length header if present
        content_length_header = request.headers.get("content-length")
        if content_length_header:
            try:
                content_length = int(content_length_header)
                if content_length > self.max_size_bytes:
                    logger.warning(
                        "Rejected oversized request based on Content-Length header",
                        content_length=content_length,
                        max_size=self.max_size_bytes,
                        correlation_id=correlation_id,
                    )
                    return self._create_413_response(correlation_id)
            except ValueError:
                pass  # Malformed content-length, proceed to streaming body verification

        # 2. Check body stream size for chunked/streaming requests
        try:
            body = await request.body()
            if len(body) > self.max_size_bytes:
                logger.warning(
                    "Rejected oversized request based on actual body stream size",
                    body_bytes=len(body),
                    max_size=self.max_size_bytes,
                    correlation_id=correlation_id,
                )
                return self._create_413_response(correlation_id)
        except Exception as exc:
            logger.error("Error reading request body in size limiter", error=str(exc), correlation_id=correlation_id)

        return await call_next(request)

    def _create_413_response(self, correlation_id: str) -> JSONResponse:
        max_mb = self.max_size_bytes // (1024 * 1024)
        error_payload = {
            "error": {
                "code": "PAYLOAD_TOO_LARGE",
                "message": f"Request payload exceeds maximum allowed size of {max_mb} MB.",
                "correlation_id": correlation_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        }
        headers = {
            "X-Correlation-ID": correlation_id,
            "X-Content-Type-Options": "nosniff",
        }
        return JSONResponse(status_code=413, content=error_payload, headers=headers)
