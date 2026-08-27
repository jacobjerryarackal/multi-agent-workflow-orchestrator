# Free-Tier Production Deployment Architecture

## 1. High-Level Topology

The Multi-Agent Workflow Orchestrator is deployed as a decoupled, production-grade cloud architecture tailored for free-tier hosting:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          PRODUCTION ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   [ Client Browser ]                                                    │
│           │                                                             │
│           │ HTTPS (Port 443)                                            │
│           ▼                                                             │
│   ┌────────────────────────────────┐                                    │
│   │        VERCEL (Edge)           │                                    │
│   │  • Next.js 14 App Router UI    │                                    │
│   │  • Serverless API Proxy        │                                    │
│   │  • Zero-Secret Client Bundle   │                                    │
│   └────────────────┬───────────────┘                                    │
│                    │                                                    │
│                    │ HTTPS Reverse Proxy Rewrites (/api/*)              │
│                    ▼                                                    │
│   ┌────────────────────────────────┐       HTTPS (TLS)                  │
│   │        RENDER (Web)            │────────────────────────┐           │
│   │  • FastAPI ASGI Container      │                        │           │
│   │  • BackgroundExecutionManager  │                        ▼           │
│   │  • Watchdog Task Supervisor    │               ┌─────────────────┐  │
│   │  • In-Process Telemetry        │               │  Google Gemini  │  │
│   └────────────────┬───────────────┘               │   API (LLM)     │  │
│                    │                               └─────────────────┘  │
│                    │ PostgreSQL Wire Protocol (SSL)                     │
│                    ▼                                                    │
│   ┌────────────────────────────────┐                                    │
│   │      MANAGED POSTGRESQL        │                                    │
│   │  • ACID State Tables           │                                    │
│   │  • JSONB Artifacts & History   │                                    │
│   │  • DB-Backed Task Leases       │                                    │
│   │  • Idempotency Unique Index    │                                    │
│   └────────────────────────────────┘                                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Boundaries & Responsibilities

| Component | Platform | Execution Model | Security Boundary |
| :--- | :--- | :--- | :--- |
| **Control Plane Frontend** | Vercel | Static & Server-Side Rendered Next.js 14 | Public client tier. Zero backend secrets. Communicates with backend via Next.js `/api/:path*` proxy. |
| **Orchestration Backend** | Render | Dockerized FastAPI ASGI Service (`python:3.11-slim`) | Private backend tier. Manages `GEMINI_API_KEY`, database credentials, and execution engine. |
| **Persistence Tier** | Render Postgres | Managed PostgreSQL 16 (ACID Relational + JSONB) | Protected relational storage with SSL enforcement and connection pool bounds. |
| **Foundation Model Provider** | Google Cloud | Google Gemini GenAI SDK (`gemini-2.5-flash`, `gemini-2.5-pro`) | Outbound TLS API calls authenticated via backend API key. |

---

## 3. Security & Invariant Guarantees

1. **Zero Secret Exposure**:
   - `GEMINI_API_KEY` and `DATABASE_URL` reside solely within Render environment variables.
   - Frontend bundles contain zero API keys or database connection strings.
2. **Deterministic Durability**:
   - Execution state persists to PostgreSQL before model invocations and upon task completion.
   - Crash recovery sweeps resume eligible workflows automatically on container reboot.
3. **Low-Latency Telemetry**:
   - In-process metrics collector serves Prometheus scrapes (`/api/v1/metrics`) and JSON snapshots (`/api/v1/telemetry`) with sub-millisecond overhead.
