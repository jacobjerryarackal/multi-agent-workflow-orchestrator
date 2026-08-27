# Production Troubleshooting Guide

This guide covers common operational alerts, failure symptoms, and resolutions.

---

## 1. HTTP 413 Payload Too Large
- **Symptom**: Client receives `{"error": {"code": "PAYLOAD_TOO_LARGE", ...}}` with status 413.
- **Cause**: Incoming request body exceeds `MAX_REQUEST_SIZE_BYTES` (default: 10 MB).
- **Resolution**: Compress input payload or upload large binaries to cloud object storage (e.g. S3 / GCS) and pass URI references in the task input.

---

## 2. HTTP 429 Too Many Requests
- **Symptom**: Client receives status 429 with `Retry-After: 60`.
- **Cause**: Client IP exceeded `RATE_LIMIT_PER_MINUTE` (default: 120 requests/minute).
- **Resolution**: Check client polling frequency. Respect `Retry-After` header. If higher throughput is needed, increase `RATE_LIMIT_PER_MINUTE` in Render environment variables.

---

## 3. Gemini Rate Limit (429 Resource Exhausted)
- **Symptom**: Task failure with error category `INFRASTRUCTURE_PROVIDER_FAILURE` and message `Gemini rate limit exceeded`.
- **Cause**: Gemini free-tier RPM/TPM quota reached.
- **Resolution**: The engine automatically applies exponential backoff with jitter up to `max_retries`. For high volume, upgrade to a paid Gemini API tier or adjust task concurrency (`MAX_PARALLEL_TASKS`).

---

## 4. Database Lease Timeouts
- **Symptom**: Task execution reclaimed by watchdog with reason `Task lease expired, reclaimed to READY`.
- **Cause**: Task execution took longer than `timeout_seconds + 30s` (e.g., slow LLM response or worker hang).
- **Resolution**: Increase `timeout_seconds` on the `TaskSpec` in the workflow definition.

---

## 5. CORS Blocked on Frontend
- **Symptom**: Browser console reports `Cross-Origin Request Blocked`.
- **Cause**: Vercel domain is not listed in `CORS_ORIGINS` environment variable on Render.
- **Resolution**: Update `CORS_ORIGINS` in Render dashboard to include the exact frontend URL (e.g. `https://your-app.vercel.app`).
