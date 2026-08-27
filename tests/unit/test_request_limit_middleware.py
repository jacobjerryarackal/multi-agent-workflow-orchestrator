"""Unit tests for RequestSizeLimitMiddleware and ProcessLocalRateLimiter."""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.middleware.request_size import RequestSizeLimitMiddleware
from app.api.middleware.rate_limit import ProcessLocalRateLimiter
from app.api.middleware.correlation import CorrelationIdMiddleware


@pytest.fixture
def size_limited_app() -> FastAPI:
    """App configured with a small 100-byte max size limit for deterministic testing."""
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware, max_size_bytes=100)

    @app.post("/echo")
    async def echo(payload: dict):
        return JSONResponse(status_code=200, content=payload)

    return app


@pytest.fixture
def rate_limited_app() -> FastAPI:
    """App configured with a tight 3 requests/minute rate limit for testing."""
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(
        ProcessLocalRateLimiter,
        requests_per_minute=2,
        burst_allowance=1,
        enabled=True,
    )

    @app.get("/api/v1/health")
    async def health():
        return JSONResponse(status_code=200, content={"status": "healthy"})

    @app.get("/api/v1/resource")
    async def resource():
        return JSONResponse(status_code=200, content={"data": "ok"})

    return app


@pytest.mark.asyncio
async def test_request_size_under_limit_allowed(size_limited_app: FastAPI):
    transport = ASGITransport(app=size_limited_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.post("/echo", json={"msg": "small"})
        assert res.status_code == 200
        assert res.json() == {"msg": "small"}


@pytest.mark.asyncio
async def test_request_size_over_limit_via_content_length_rejected(size_limited_app: FastAPI):
    transport = ASGITransport(app=size_limited_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Simulated large content length
        headers = {"Content-Length": "500", "Content-Type": "application/json"}
        res = await client.post("/echo", headers=headers, content=b'{"test": "dummy"}')
        assert res.status_code == 413
        data = res.json()
        assert "error" in data
        assert data["error"]["code"] == "PAYLOAD_TOO_LARGE"
        assert "X-Correlation-ID" in res.headers


@pytest.mark.asyncio
async def test_request_size_over_limit_via_actual_body_rejected(size_limited_app: FastAPI):
    transport = ASGITransport(app=size_limited_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        oversized_data = {"payload": "x" * 200}
        res = await client.post("/echo", json=oversized_data)
        assert res.status_code == 413
        data = res.json()
        assert data["error"]["code"] == "PAYLOAD_TOO_LARGE"


@pytest.mark.asyncio
async def test_rate_limiter_allows_under_quota(rate_limited_app: FastAPI):
    transport = ASGITransport(app=rate_limited_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res1 = await client.get("/api/v1/resource")
        res2 = await client.get("/api/v1/resource")
        assert res1.status_code == 200
        assert res2.status_code == 200


@pytest.mark.asyncio
async def test_rate_limiter_bypasses_health_and_metrics(rate_limited_app: FastAPI):
    transport = ASGITransport(app=rate_limited_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Health checks should never be rate limited
        for _ in range(10):
            res = await client.get("/api/v1/health")
            assert res.status_code == 200


@pytest.mark.asyncio
async def test_rate_limiter_blocks_after_quota_exceeded(rate_limited_app: FastAPI):
    transport = ASGITransport(app=rate_limited_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Quota is 2 + burst 1 = 3 requests
        r1 = await client.get("/api/v1/resource")
        r2 = await client.get("/api/v1/resource")
        r3 = await client.get("/api/v1/resource")
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 200

        # 4th request must be throttled with HTTP 429
        r4 = await client.get("/api/v1/resource")
        assert r4.status_code == 429
        assert r4.json()["error"]["code"] == "TOO_MANY_REQUESTS"
        assert r4.headers.get("Retry-After") == "60"
