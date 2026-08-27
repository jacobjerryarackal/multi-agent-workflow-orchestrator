# Production Environment Variables Reference

This document provides the definitive reference for all environment variables used by the Multi-Agent Workflow Orchestrator.

---

## 1. Backend Environment Variables (Render Web Service)

| Variable Name | Required | Default Value | Description / Security Classification |
| :--- | :--- | :--- | :--- |
| `APP_NAME` | No | `MultiAgentWorkflowOrchestrator` | Application identification string for logs and root metadata. |
| `APP_ENV` | Yes | `production` | Environment tier: `development`, `staging`, or `production`. |
| `LOG_LEVEL` | No | `INFO` | Logging threshold (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `DEBUG` | No | `false` | Enables interactive debugging (must be `false` in production). |
| `HOST` | No | `0.0.0.0` | ASGI bind IP address. |
| `PORT` | No | `8000` | Port listened to by Uvicorn ASGI server. |
| `CORS_ORIGINS` | Yes | Localhost | Comma-separated list of allowed web origins (e.g. `https://your-app.vercel.app`). |
| `DATABASE_URL` | Yes | None | **CRITICAL SECRET**: PostgreSQL connection URI (`postgresql+asyncpg://...`). |
| `DATABASE_POOL_SIZE` | No | `5` | Core persistent async connection pool capacity. |
| `DATABASE_MAX_OVERFLOW`| No | `5` | Maximum overflow connections during concurrent bursts. |
| `DATABASE_POOL_TIMEOUT` | No | `30` | Seconds to wait before failing connection acquisition. |
| `DATABASE_POOL_RECYCLE` | No | `1800` | Connection recycling timeout in seconds (prevents stale TCP drops). |
| `DATABASE_POOL_PRE_PING`| No | `true` | Tests connection validity prior to checkout. |
| `GEMINI_API_KEY` | Yes | None | **CRITICAL SECRET**: Google Gemini GenAI SDK API key. |
| `DEFAULT_MODEL_NAME` | No | `gemini-2.5-flash` | Standard model for agent inference tasks. |
| `REASONING_MODEL_NAME`| No | `gemini-2.5-pro` | Advanced model for complex analysis and evaluations. |
| `MAX_WORKFLOW_DURATION_SECONDS` | No | `600` | Global workflow execution hard timeout (seconds). |
| `MAX_TASK_DURATION_SECONDS` | No | `60` | Per-task execution hard timeout (seconds). |
| `MAX_PARALLEL_TASKS` | No | `5` | Maximum concurrent tasks dispatched in a single DAG cycle. |
| `MAX_TASK_RETRIES` | No | `3` | Maximum automatic execution attempts for failed tasks. |
| `MAX_REQUEST_SIZE_BYTES` | No | `10485760` (10 MB) | Maximum incoming request body size limit. |
| `RATE_LIMIT_ENABLED` | No | `true` | Enables in-process sliding-window rate limiting. |
| `RATE_LIMIT_PER_MINUTE`| No | `120` | Maximum allowed API requests per minute per client IP. |
| `RATE_LIMIT_BURST` | No | `30` | Burst request buffer above per-minute allowance. |

---

## 2. Frontend Environment Variables (Vercel)

| Variable Name | Required | Example Value | Description |
| :--- | :--- | :--- | :--- |
| `BACKEND_API_URL` | Yes | `https://orchestrator-api.onrender.com` | Target URL of the backend FastAPI service on Render. Used by Next.js server-side rewrites. |

> **IMPORTANT**: `GEMINI_API_KEY` and `DATABASE_URL` MUST NOT be set on Vercel. The Next.js frontend has zero direct database or LLM access.
