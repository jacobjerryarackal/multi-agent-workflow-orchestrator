"""Request correlation ID middleware and context management."""

import uuid
from contextvars import ContextVar
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# Context variable to hold the correlation ID for the lifetime of a request
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")

CORRELATION_ID_HEADER = "X-Correlation-ID"


def get_correlation_id() -> str:
    """Retrieves the correlation ID for the active request context."""
    cid = correlation_id_var.get()
    if not cid:
        cid = uuid.uuid4().hex
        correlation_id_var.set(cid)
    return cid


def set_correlation_id(correlation_id: str) -> None:
    """Explicitly sets the correlation ID for the current context."""
    correlation_id_var.set(correlation_id)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware ensuring every HTTP request has a unique correlation ID.
    Reads X-Correlation-ID from the client request or generates a new UUIDv4.
    Injects the correlation ID into contextvars and response headers.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 1. Read existing header or generate a new UUID
        client_correlation_id: Optional[str] = request.headers.get(CORRELATION_ID_HEADER)
        if client_correlation_id and client_correlation_id.strip():
            correlation_id = client_correlation_id.strip()
        else:
            correlation_id = uuid.uuid4().hex

        # 2. Store in context variable and request state
        token = correlation_id_var.set(correlation_id)
        request.state.correlation_id = correlation_id

        try:
            try:
                response = await call_next(request)
            except Exception as exc:
                # Ensure unexpected exceptions produce a sanitized response with correlation ID
                from ..errors import orchestrator_domain_exception_handler, unhandled_exception_handler
                from ...core.exceptions import OrchestratorException
                if isinstance(exc, OrchestratorException):
                    response = await orchestrator_domain_exception_handler(request, exc)
                else:
                    response = await unhandled_exception_handler(request, exc)

            # 3. Add correlation header to response
            response.headers[CORRELATION_ID_HEADER] = correlation_id
            return response
        finally:
            correlation_id_var.reset(token)
