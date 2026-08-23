"""FastAPI API package aggregation."""

from .health import health_router
from .errors import register_exception_handlers, create_error_response, ErrorEnvelope
from .middleware import (
    CorrelationIdMiddleware,
    SecurityHeadersMiddleware,
    get_correlation_id,
    set_correlation_id,
)

__all__ = [
    "health_router",
    "register_exception_handlers",
    "create_error_response",
    "ErrorEnvelope",
    "CorrelationIdMiddleware",
    "SecurityHeadersMiddleware",
    "get_correlation_id",
    "set_correlation_id",
]
