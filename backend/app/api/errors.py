"""Centralized API error contract and exception handlers."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Union
import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..core.exceptions import (
    OrchestratorException,
    SchemaValidationError,
    WorkflowValidationError,
    CyclicDependencyError,
    WorkflowNotFoundError,
    AgentNotFoundError,
    StateTransitionError,
    ApprovalGateError,
    ArtifactIntegrityError,
    CircuitBreakerOpenError,
    ModelProviderError,
    EvaluatorError,
    WorkflowTimeoutError,
    TaskExecutionTimeoutError,
)
from .middleware.correlation import get_correlation_id

logger = structlog.get_logger(__name__)


class ErrorDetail(BaseModel):
    """Structured error payload definition for API responses."""
    code: str
    message: str
    correlation_id: str
    timestamp: str
    details: Dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    """Uniform top-level JSON response envelope for all API errors."""
    error: ErrorDetail


def create_error_response(
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
) -> JSONResponse:
    """Helper creating standard error envelope JSONResponses."""
    formatted_details: Dict[str, Any] = {}
    if isinstance(details, dict):
        formatted_details = details
    elif isinstance(details, (list, tuple)):
        formatted_details = {"errors": list(details)}
    elif details is not None:
        formatted_details = {"info": str(details)}

    correlation_id = get_correlation_id()
    now_iso = datetime.now(timezone.utc).isoformat()

    envelope = ErrorEnvelope(
        error=ErrorDetail(
            code=code,
            message=message,
            correlation_id=correlation_id,
            timestamp=now_iso,
            details=formatted_details,
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=envelope.model_dump(),
    )


async def orchestrator_domain_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Maps custom domain exceptions to standard HTTP status codes and machine-readable error codes."""
    correlation_id = get_correlation_id()
    
    # 422 Validation
    if isinstance(exc, (SchemaValidationError, WorkflowValidationError, CyclicDependencyError)):
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        code = "VALIDATION_ERROR"
    # 404 Not Found
    elif isinstance(exc, (WorkflowNotFoundError, AgentNotFoundError)):
        status_code = status.HTTP_404_NOT_FOUND
        code = "RESOURCE_NOT_FOUND"
    # 409 Conflict
    elif isinstance(exc, StateTransitionError):
        status_code = status.HTTP_409_CONFLICT
        code = "INVALID_STATE_TRANSITION"
    # 403 Forbidden
    elif isinstance(exc, ApprovalGateError):
        status_code = status.HTTP_403_FORBIDDEN
        code = "APPROVAL_GATE_VIOLATION"
    # 504 Timeout
    elif isinstance(exc, (WorkflowTimeoutError, TaskExecutionTimeoutError)):
        status_code = status.HTTP_504_GATEWAY_TIMEOUT
        code = "EXECUTION_TIMED_OUT"
    # 503 Provider / Service Unavailable
    elif isinstance(exc, (CircuitBreakerOpenError, ModelProviderError, EvaluatorError)):
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        code = "PROVIDER_UNAVAILABLE"
    # 500 Artifact Integrity
    elif isinstance(exc, ArtifactIntegrityError):
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        code = "ARTIFACT_INTEGRITY_ERROR"
    else:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        code = "ORCHESTRATOR_ERROR"

    msg = getattr(exc, "message", str(exc))
    exc_details = getattr(exc, "details", {})

    logger.warning(
        "Domain exception handled",
        error_code=code,
        status_code=status_code,
        message=msg,
        correlation_id=correlation_id,
        path=request.url.path,
    )

    return create_error_response(
        status_code=status_code,
        code=code,
        message=msg,
        details=exc_details,
    )


async def request_validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handles FastAPI/Pydantic request body and query parameter validation failures."""
    correlation_id = get_correlation_id()
    validation_errors = getattr(exc, "errors", lambda: [])()
    logger.info(
        "Request validation error",
        correlation_id=correlation_id,
        path=request.url.path,
        errors=validation_errors,
    )
    return create_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="REQUEST_VALIDATION_ERROR",
        message="Request payload failed schema validation.",
        details=validation_errors,
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handles standard Starlette / FastAPI HTTPExceptions."""
    correlation_id = get_correlation_id()
    status_code = getattr(exc, "status_code", 500)
    detail = getattr(exc, "detail", str(exc))

    code = "HTTP_ERROR"
    if status_code == status.HTTP_404_NOT_FOUND:
        code = "RESOURCE_NOT_FOUND"
    elif status_code == status.HTTP_401_UNAUTHORIZED:
        code = "UNAUTHORIZED"
    elif status_code == status.HTTP_403_FORBIDDEN:
        code = "FORBIDDEN"

    logger.info(
        "HTTP exception handled",
        status_code=status_code,
        code=code,
        detail=detail,
        correlation_id=correlation_id,
        path=request.url.path,
    )

    return create_error_response(
        status_code=status_code,
        code=code,
        message=str(detail),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all exception handler for unexpected server-side errors.
    CRITICAL: Sanitizes stack traces, secrets, and raw internals from response.
    """
    correlation_id = get_correlation_id()
    logger.exception(
        "Unhandled server exception",
        correlation_id=correlation_id,
        path=request.url.path,
        exc_info=exc,
    )

    return create_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected server error occurred. Please reference correlation ID.",
        details={"correlation_id": correlation_id},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Registers centralized exception handlers to a FastAPI application instance."""
    app.add_exception_handler(OrchestratorException, orchestrator_domain_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
