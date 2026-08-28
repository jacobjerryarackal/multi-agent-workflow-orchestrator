"""Unit tests for Phase 6.1 FastAPI Application Factory, Middleware, and Foundation."""

import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI, APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import create_app, lifespan
from app.core.config import Settings
from app.core.exceptions import (
    WorkflowValidationError,
    WorkflowNotFoundError,
    StateTransitionError,
    ApprovalGateError,
    ArtifactIntegrityError,
    ModelProviderError,
    WorkflowTimeoutError,
)
from app.api.dependencies import (
    get_agent_registry,
    get_model_provider,
    get_evaluator,
    get_workflow_repo,
    get_execution_repo,
    get_event_repo,
    get_artifact_repo,
    get_db_session,
)


@pytest.fixture
def app_instance(db_session: AsyncSession) -> FastAPI:
    """Creates a FastAPI test application with test database session dependency override."""
    app = create_app()

    # Override get_db_session to use test SQLite db_session
    async def override_get_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    return app


@pytest_asyncio.fixture
async def client(app_instance: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Provides an AsyncClient for test requests against the FastAPI app."""
    transport = ASGITransport(app=app_instance)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


# =============================================================================
# 1. APPLICATION FACTORY & LIFESPAN TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_application_factory_and_root_endpoint(client: AsyncClient):
    """Verifies create_app() produces a functioning application with root endpoint."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert data["docs_url"] == "/docs"
    assert data["health_url"] == "/api/v1/health"
    assert "correlation_id" in data


@pytest.mark.asyncio
async def test_lifespan_startup_shutdown(app_instance: FastAPI):
    """Verifies that lifespan startup and shutdown context manager executes cleanly."""
    async with lifespan(app_instance):
        assert app_instance.title == "Multi-Agent Workflow Orchestrator API"


# =============================================================================
# 2. CORRELATION ID MIDDLEWARE TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_correlation_id_generated_when_absent(client: AsyncClient):
    """When client provides no X-Correlation-ID, server generates one and returns it in header and body."""
    response = await client.get("/")
    assert response.status_code == 200
    corr_id = response.headers.get("X-Correlation-ID")
    assert corr_id is not None
    assert len(corr_id) > 10
    assert response.json()["correlation_id"] == corr_id


@pytest.mark.asyncio
async def test_correlation_id_preserved_when_supplied(client: AsyncClient):
    """When client provides X-Correlation-ID, server preserves the exact identifier."""
    custom_id = "test-custom-correlation-999"
    response = await client.get("/", headers={"X-Correlation-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("X-Correlation-ID") == custom_id
    assert response.json()["correlation_id"] == custom_id


# =============================================================================
# 3. SECURITY HEADERS MIDDLEWARE TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_security_headers_applied(client: AsyncClient):
    """Verifies that SecurityHeadersMiddleware attaches standard hardening headers."""
    response = await client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-XSS-Protection"] == "1; mode=block"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert "geolocation=()" in response.headers["Permissions-Policy"]


# =============================================================================
# 4. CORS CONFIGURATION TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_cors_preflight_allowed_origin(client: AsyncClient):
    """Verifies that OPTIONS preflight request from allowed origin returns CORS headers."""
    headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type, X-Correlation-ID",
    }
    response = await client.options("/api/v1/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert response.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.asyncio
async def test_cors_disallowed_origin(client: AsyncClient):
    """Verifies that requests from untrusted origins do not receive allow-origin header."""
    headers = {
        "Origin": "http://evil-untrusted-site.com",
        "Access-Control-Request-Method": "POST",
    }
    response = await client.options("/api/v1/health", headers=headers)
    assert response.headers.get("access-control-allow-origin") is None


# =============================================================================
# 5. ERROR HANDLING & ENVELOPE TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_error_handling_domain_exceptions(app_instance: FastAPI):
    """Verifies that custom domain exceptions map to expected status codes and standard envelopes."""
    test_router = APIRouter()

    @test_router.get("/test-validation-error")
    async def route_val():
        raise WorkflowValidationError("Invalid DAG topology", details={"node": "t1"})

    @test_router.get("/test-not-found-error")
    async def route_nf():
        raise WorkflowNotFoundError("Workflow 'wf-123' does not exist")

    @test_router.get("/test-conflict-error")
    async def route_conflict():
        raise StateTransitionError("Cannot transition COMPLETED to RUNNING")

    @test_router.get("/test-forbidden-error")
    async def route_forbidden():
        raise ApprovalGateError("Approval rejected by policy")

    @test_router.get("/test-provider-error")
    async def route_provider():
        raise ModelProviderError("Gemini API rate limited")

    @test_router.get("/test-timeout-error")
    async def route_timeout():
        raise WorkflowTimeoutError("Workflow duration exceeded limit")

    @test_router.get("/test-artifact-error")
    async def route_artifact():
        raise ArtifactIntegrityError("Checksum verification failed")

    @test_router.get("/test-unhandled-error")
    async def route_unhandled():
        raise RuntimeError("Internal database password secret leaked")

    app_instance.include_router(test_router)
    transport = ASGITransport(app=app_instance)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Validation -> 422
        r_val = await client.get("/test-validation-error", headers={"X-Correlation-ID": "cid-val"})
        assert r_val.status_code == 422
        body = r_val.json()["error"]
        assert body["code"] == "VALIDATION_ERROR"
        assert body["message"] == "Invalid DAG topology"
        assert body["correlation_id"] == "cid-val"
        assert body["details"]["node"] == "t1"

        # 2. Not Found -> 404
        r_nf = await client.get("/test-not-found-error")
        assert r_nf.status_code == 404
        assert r_nf.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

        # 3. Conflict -> 409
        r_cf = await client.get("/test-conflict-error")
        assert r_cf.status_code == 409
        assert r_cf.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

        # 4. Forbidden -> 403
        r_fb = await client.get("/test-forbidden-error")
        assert r_fb.status_code == 403
        assert r_fb.json()["error"]["code"] == "APPROVAL_GATE_VIOLATION"

        # 5. Service Unavailable -> 503
        r_pr = await client.get("/test-provider-error")
        assert r_pr.status_code == 503
        assert r_pr.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"

        # 6. Gateway Timeout -> 504
        r_to = await client.get("/test-timeout-error")
        assert r_to.status_code == 504
        assert r_to.json()["error"]["code"] == "EXECUTION_TIMED_OUT"

        # 7. Artifact Integrity -> 500
        r_art = await client.get("/test-artifact-error")
        assert r_art.status_code == 500
        assert r_art.json()["error"]["code"] == "ARTIFACT_INTEGRITY_ERROR"

        # 8. Unhandled Error -> 500 Sanitized
        r_un = await client.get("/test-unhandled-error")
        assert r_un.status_code == 500
        err_body = r_un.json()["error"]
        assert err_body["code"] == "INTERNAL_SERVER_ERROR"
        # Must NOT expose raw exception string "password secret"
        assert "password secret" not in err_body["message"]
        assert "correlation_id" in err_body


# =============================================================================
# 6. HEALTH ENDPOINT TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_health_endpoint_healthy(client: AsyncClient):
    """Verifies that GET /api/v1/health returns structured component health information."""
    response = await client.get("/api/v1/health")
    assert response.status_code in (200, 200)
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert "database" in data["components"]
    assert data["components"]["database"]["status"] == "healthy"
    assert "agent_registry" in data["components"]
    assert "model_provider" in data["components"]
    assert len(data["components"]["agent_registry"]["details"]["agents"]) == 5


@pytest.mark.asyncio
async def test_health_endpoint_database_failure_returns_503(app_instance: FastAPI):
    """When database connectivity fails, health endpoint returns 503 Unavailable."""
    class FailingSession:
        async def execute(self, stmt):
            raise ConnectionError("PostgreSQL host unreachable")

    async def override_failing_session():
        yield FailingSession()

    app_instance.dependency_overrides[get_db_session] = override_failing_session
    transport = ASGITransport(app=app_instance)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unavailable"
        assert data["components"]["database"]["status"] == "unavailable"


# =============================================================================
# 7. DEPENDENCY INJECTION INITIALIZATION TESTS
# =============================================================================

def test_dependency_providers():
    """Verifies that singleton dependency providers instantiate successfully."""
    registry = get_agent_registry()
    assert len(registry.list_agents()) == 5

    provider = get_model_provider()
    assert provider is not None

    evaluator = get_evaluator()
    assert evaluator is not None


@pytest.mark.asyncio
async def test_repository_dependencies(db_session: AsyncSession):
    """Verifies repository factory dependencies."""
    wf_repo = get_workflow_repo(db_session)
    exec_repo = get_execution_repo(db_session)
    event_repo = get_event_repo(db_session)
    art_repo = get_artifact_repo(db_session)

    assert wf_repo is not None
    assert exec_repo is not None
    assert event_repo is not None
    assert art_repo is not None


# =============================================================================
# 8. ADDITIONAL COVERAGE TESTS FOR ERRORS & CORRELATION HELPERS
# =============================================================================

@pytest.mark.asyncio
async def test_request_validation_error_handling(app_instance: FastAPI):
    """Verifies that Pydantic request body validation errors return 422 standard envelope."""
    from pydantic import BaseModel
    test_router = APIRouter()

    class StrictSchema(BaseModel):
        required_int: int
        required_str: str

    @test_router.post("/test-pydantic-validation")
    async def route_pydantic_val(payload: StrictSchema):
        return {"status": "ok"}

    app_instance.include_router(test_router)
    transport = ASGITransport(app=app_instance)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Missing required_str, invalid required_int type
        response = await client.post("/test-pydantic-validation", json={"required_int": "invalid"})
        assert response.status_code == 422
        body = response.json()["error"]
        assert body["code"] == "REQUEST_VALIDATION_ERROR"
        assert len(body["details"]["errors"]) > 0


@pytest.mark.asyncio
async def test_http_exceptions_handling(app_instance: FastAPI):
    """Verifies that standard HTTPExceptions (401, 403, 404) format into standard envelope."""
    from fastapi import HTTPException
    test_router = APIRouter()

    @test_router.get("/test-401")
    async def route_401():
        raise HTTPException(status_code=401, detail="Invalid API key credentials")

    @test_router.get("/test-403")
    async def route_403():
        raise HTTPException(status_code=403, detail="Access denied")

    app_instance.include_router(test_router)
    transport = ASGITransport(app=app_instance)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        r401 = await client.get("/test-401")
        assert r401.status_code == 401
        assert r401.json()["error"]["code"] == "UNAUTHORIZED"

        r403 = await client.get("/test-403")
        assert r403.status_code == 403
        assert r403.json()["error"]["code"] == "FORBIDDEN"


def test_correlation_helpers_direct():
    """Verifies direct context variable get/set functions."""
    from app.api.middleware.correlation import get_correlation_id, set_correlation_id
    set_correlation_id("manual-test-id-12345")
    assert get_correlation_id() == "manual-test-id-12345"


def test_create_error_response_formats():
    """Verifies create_error_response handles string and list details."""
    from app.api.errors import create_error_response
    r1 = create_error_response(status_code=400, code="ERR_1", message="Msg", details="Simple string detail")
    assert r1.status_code == 400

    r2 = create_error_response(status_code=400, code="ERR_2", message="Msg", details=["err1", "err2"])
    assert r2.status_code == 400


def test_normalize_database_url():
    """Verifies database URL normalization for asyncpg and aiosqlite."""
    from app.core.config import normalize_database_url
    from sqlalchemy.dialects.postgresql.asyncpg import PGDialect_asyncpg
    from sqlalchemy.engine.url import make_url

    # Neon URL with sslmode and channel_binding
    neon_raw = "postgresql://user:pass@ep-test.neon.tech/neondb?sslmode=require&channel_binding=require"
    normalized = normalize_database_url(neon_raw)
    assert normalized == "postgresql+asyncpg://user:pass@ep-test.neon.tech/neondb?ssl=require"

    # Verify asyncpg dialect connect kwargs
    d = PGDialect_asyncpg()
    args, kwargs = d.create_connect_args(make_url(normalized))
    assert kwargs.get("ssl") == "require"
    assert "sslmode" not in kwargs
    assert "channel_binding" not in kwargs
    assert "gssencmode" not in kwargs

    # postgres:// prefix
    assert normalize_database_url("postgres://user:pass@ep-test.neon.tech/neondb?sslmode=verify-full&channel_binding=require&gssencmode=disable") == (
        "postgresql+asyncpg://user:pass@ep-test.neon.tech/neondb?ssl=require"
    )

    # Already normalized URL
    assert normalize_database_url("postgresql+asyncpg://user:pass@localhost:5432/db") == (
        "postgresql+asyncpg://user:pass@localhost:5432/db"
    )

    # SQLite normalization
    assert normalize_database_url("sqlite:///./test.db") == "sqlite+aiosqlite:///./test.db"
    assert normalize_database_url("sqlite+aiosqlite:///./test.db") == "sqlite+aiosqlite:///./test.db"

    # Empty string pass-through
    assert normalize_database_url("") == ""


def test_settings_database_url_validation():
    """Verifies Settings model automatically normalizes DATABASE_URL on instantiation."""
    from app.core.config import Settings

    s = Settings(DATABASE_URL="postgresql://user:secret@ep-neon.tech/db?sslmode=require&channel_binding=require")
    assert s.DATABASE_URL == "postgresql+asyncpg://user:secret@ep-neon.tech/db?ssl=require"


