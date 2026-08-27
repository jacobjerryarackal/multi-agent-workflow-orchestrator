# Production Operations & Telemetry Guide

This document describes runtime operations, telemetry monitoring, and background supervisor management.

---

## 1. Health & Telemetry Endpoints

The backend provides three real-time diagnostic endpoints:

### `GET /api/v1/health` (Readiness / Liveness Probe)
Returns overall health status (`healthy`, `degraded`, or `unavailable`) and component diagnostic details for:
- **`database`**: PostgreSQL connectivity, async connection pool checkout count, pool size, overflow.
- **`agent_registry`**: Count of registered agent tools.
- **`model_provider`**: Gemini API configuration state and default model name.
- **`background_manager`**: In-flight workflow execution count and watchdog supervisor status.

### `GET /api/v1/telemetry` (Structured JSON Metrics Snapshot)
Returns instantaneous values of all registered:
- **`counters`**: HTTP requests, workflow starts/completions/failures, task attempts/retries, token usage, artifact creations.
- **`gauges`**: Active background tasks, checked out database connections, pool overflow.
- **`histograms`**: Request latency, execution duration, quality evaluation scores.

### `GET /api/v1/metrics` (Prometheus Exposition)
Outputs standard OpenMetrics/Prometheus formatted text for automated metric scrapers (Grafana Agent, Prometheus, Datadog OpenMetrics integration).

---

## 2. Background Execution & Watchdog Supervision

- **Execution Dispatching**: Workflows are dispatched as non-blocking `asyncio.Task` coroutines managed by `BackgroundExecutionManager`.
- **Task Lease Watchdog**: A background supervisor runs periodically (default: every 10 seconds), querying for tasks whose lease has expired (`lease_until < NOW()`). Expired tasks are safely reclaimed to `READY` state or terminally failed if retry budgets are exhausted.
- **Startup Recovery**: On container startup / reboot, the engine automatically sweeps for stranded active executions and resumes scheduling.
