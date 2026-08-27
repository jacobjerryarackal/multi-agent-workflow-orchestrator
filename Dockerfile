# ==============================================================================
# Multi-Agent Workflow Orchestrator - Production Container (Multi-stage Build)
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Builder (Dependency installation and compilation)
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build tools needed for native extensions (e.g. asyncpg, greenlet)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency manifest
COPY requirements.txt .

# Install dependencies into a virtual environment
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ------------------------------------------------------------------------------
# Stage 2: Production Runtime (Minimal footprint, Non-root user)
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# Install libpq runtime library for PostgreSQL connectivity & curl for HEALTHCHECK
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root application user
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m appuser

WORKDIR /app

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app:/app/backend" \
    PYTHONUNBUFFERED="1" \
    PYTHONDONTWRITEBYTECODE="1" \
    HOST="0.0.0.0" \
    PORT="8000" \
    APP_ENV="production"

# Copy application source code and Alembic migrations
COPY --chown=appuser:appgroup backend /app/backend

# Switch to non-root execution user
USER appuser

# Expose HTTP port
EXPOSE 8000

# Container healthcheck querying the standardized /api/v1/health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/api/v1/health || exit 1

# Start production ASGI server with single-worker process management for free-tier durability
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--lifespan", "on"]
