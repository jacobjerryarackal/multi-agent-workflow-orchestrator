# Security Architecture & Threat Model

**Document:** STRIDE Threat Analysis, Trust Boundaries & Security Controls  
**Status:** Approved Architecture (Day 0)  

---

## 1. System Trust Boundaries & Data Flow

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│ [UNTRUSTED ZONE] Browser Frontend (Next.js Control Plane)                         │
└────────────────────────────────────────┬──────────────────────────────────────────┘
                                         │ HTTPS / Bearer Token / Strict CORS
                                         ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│ [DMZ / API GATEWAY] FastAPI Ingress (Authentication, Rate Limiting, Input Filter)  │
└────────────────────────────────────────┬──────────────────────────────────────────┘
                                         │ Internal Python Process Calls
                                         ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│ [TRUSTED BACKEND] Orchestration Engine, State Machine, Agent Registry             │
└──────────────┬─────────────────────────┬─────────────────────────┬────────────────┘
               │ TLS 1.3                 │ Outbound HTTPS          │ Internal IPC
               ▼                         ▼                         ▼
┌───────────────────────────┐ ┌─────────────────────┐ ┌─────────────────────────────┐
│ Managed PostgreSQL (Prod) │ │ Google Gemini API   │ │ Future Adapters             │
│ (State, Audit, Artifacts) │ │ (API Key in backend)│ │ (MemoryOps / EvalForge)     │
└───────────────────────────┘ └─────────────────────┘ └─────────────────────────────┘
```

---

## 2. STRIDE Threat Analysis Matrix

| Threat Category | Potential Attack Vector | Impact | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| **Spoofing** | Attacker impersonates an operator to approve a high-stakes task gate. | Unauthorized workflow progress or data alteration. | JWT-based authentication, user attribution in `WorkflowEvent.actor`, RBAC on approval endpoints. |
| **Tampering** | Man-in-the-middle or malicious payload alters task artifact content. | Corrupted downstream reasoning, hallucinated pipeline output. | SHA-256 content hashes generated upon artifact creation; verified before passing to downstream tasks. |
| **Repudiation** | Operator denies approving or rejecting a workflow execution gate. | Lack of compliance audit trail and operational accountability. | Immutable `workflow_events` log storing user identity, timestamp, IP, and cryptographic signature in PostgreSQL. |
| **Information Disclosure** | LLM API keys or sensitive tenant data leak to frontend client. | Severe credential compromise and data breach. | API keys stored strictly in server-side environment variables; frontend receives sanitized DTOs only. |
| **Denial of Service** | "Loop Bomb" / recursive DAG or unbounded parallel task spam. | Exhaustion of server CPU/memory and LLM API budget depletion. | DAG cycle detection at registration, strict `max_parallel_tasks` (20), global workflow timeout (10m), rate limiting on API. |
| **Elevation of Privilege** | Prompt injection in task input tricks agent into executing system tools. | Agent outputs unauthorized commands or bypasses validation. | Structured outputs enforced via JSON schemas; no arbitrary code execution / shell tools enabled in v1. |

---

## 3. Security Policy Invariants

1. **Zero Secret Leakage to Client**: Gemini API keys and database credentials NEVER enter frontend bundles or API responses.
2. **No Arbitrary Code Execution**: Agents generate structured data, text, and JSON artifacts. Agents are prohibited from invoking arbitrary shell commands or untrusted dynamic code execution (`eval`).
3. **Strict Workflow Schema Validation**: All workflow definitions are statically validated before being accepted into the registry.
4. **Isolated Transient Storage**: Artifacts and context data are isolated per workflow execution ID, preventing cross-tenant or cross-workflow data contamination.
