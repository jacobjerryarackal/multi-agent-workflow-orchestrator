"""
PostgreSQL integration tests verifying database connection pooling configuration,
pool pre-ping, connection recycling, and safe connection release under concurrency.
"""

import asyncio
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import AsyncAdaptedQueuePool

from app.core.config import settings

POSTGRES_TEST_URL = "postgresql+asyncpg://postgres:12345678@localhost:5432/orchestrator_test_db"


@pytest.mark.asyncio
async def test_connection_pool_configuration_and_pre_ping():
    """
    Verifies that the PostgreSQL async engine is properly configured with:
    - AsyncAdaptedQueuePool
    - Configured pool_size and max_overflow
    - Configured pool_recycle
    - pool_pre_ping enabled
    """
    engine = create_async_engine(
        POSTGRES_TEST_URL,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_timeout=settings.DATABASE_POOL_TIMEOUT,
        pool_recycle=settings.DATABASE_POOL_RECYCLE,
        pool_pre_ping=settings.DATABASE_POOL_PRE_PING,
    )

    # Verify pool type and configuration parameters
    pool = engine.pool
    assert isinstance(pool, AsyncAdaptedQueuePool)
    assert pool.size() == settings.DATABASE_POOL_SIZE
    assert pool._max_overflow == settings.DATABASE_MAX_OVERFLOW
    assert pool._recycle == settings.DATABASE_POOL_RECYCLE
    assert pool._pre_ping is True

    # Test executing a query on a healthy connection
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT 1"))
        assert res.scalar_one() == 1

    # Verify connection was returned to pool
    assert pool.checkedout() == 0  # type: ignore[reportAttributeAccessIssue]

    await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_sessions_acquire_and_release_connections_cleanly():
    """
    Simulates 10 concurrent database sessions executing queries.
    Verifies that all connections are returned to the pool without connection leaks.
    """
    engine = create_async_engine(
        POSTGRES_TEST_URL,
        pool_size=5,
        max_overflow=5,
        pool_timeout=30,
        pool_recycle=1800,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def run_query(worker_id: int):
        async with session_factory() as session:
            res = await session.execute(text("SELECT CAST(:worker_id AS INTEGER) AS w"), {"worker_id": worker_id})
            val = res.scalar_one()
            # Small delay to simulate in-flight concurrency
            await asyncio.sleep(0.05)
            return val

    # Run 10 concurrent queries
    results = await asyncio.gather(*[run_query(i) for i in range(10)])
    assert sorted(results) == list(range(10))

    # All connections must be returned to pool (checkedout == 0)
    assert engine.pool.checkedout() == 0  # type: ignore[reportAttributeAccessIssue]

    await engine.dispose()
