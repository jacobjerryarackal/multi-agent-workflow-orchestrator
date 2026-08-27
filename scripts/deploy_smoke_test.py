#!/usr/bin/env python3
"""
Production Deployment Smoke Test Script.

Validates operational health, connectivity, security headers, correlation IDs,
agent catalog, telemetry, and error formatting against local or remote deployments.

Usage:
    python scripts/deploy_smoke_test.py --url http://127.0.0.1:8000
    python scripts/deploy_smoke_test.py --url https://orchestrator-api.onrender.com
"""

import argparse
import sys
import uuid
from typing import Tuple
import httpx


def run_smoke_tests(base_url: str) -> bool:
    base_url = base_url.rstrip("/")
    print(f"\n==================================================")
    print(f"DEPLOYMENT PRE-FLIGHT SMOKE TEST")
    print(f"Target: {base_url}")
    print(f"==================================================\n")

    passed = 0
    total = 10

    client = httpx.Client(base_url=base_url, timeout=15.0)

    # Check 1: Root Service Metadata (with warm-up retry)
    for attempt in range(5):
        try:
            res = client.get("/")
            if res.status_code == 200 and "name" in res.json():
                print("  [PASS] 1. Root Service Metadata (GET /)")
                passed += 1
                break
        except Exception:
            if attempt < 4:
                import time
                time.sleep(0.5)
            else:
                print("  [FAIL] 1. Root Service Metadata failed to connect after 5 attempts")

    # Check 2: System Health & Component Status
    try:
        res = client.get("/api/v1/health")
        if res.status_code == 200:
            data = res.json()
            status = data.get("status", "unknown")
            components = data.get("components", {})
            db_status = components.get("database", {}).get("status", "unknown")
            print(f"  [PASS] 2. Health & Component Readiness (status={status}, db={db_status})")
            passed += 1
        else:
            print(f"  [FAIL] 2. Health check returned HTTP {res.status_code}")
    except Exception as exc:
        print(f"  [FAIL] 2. Health check failed: {exc}")

    # Check 3: Correlation ID Echo & Propagation
    try:
        custom_cid = f"smoke-test-{uuid.uuid4().hex[:8]}"
        res = client.get("/api/v1/health", headers={"X-Correlation-ID": custom_cid})
        returned_cid = res.headers.get("X-Correlation-ID")
        if returned_cid == custom_cid:
            print("  [PASS] 3. Correlation ID Propagation (X-Correlation-ID preserved)")
            passed += 1
        else:
            print(f"  [FAIL] 3. Correlation ID mismatch: expected {custom_cid}, got {returned_cid}")
    except Exception as exc:
        print(f"  [FAIL] 3. Correlation ID check failed: {exc}")

    # Check 4: Defensive Security Headers
    try:
        res = client.get("/api/v1/health")
        headers = res.headers
        has_nosniff = headers.get("X-Content-Type-Options") == "nosniff"
        has_frame_deny = headers.get("X-Frame-Options") == "DENY"
        if has_nosniff and has_frame_deny:
            print("  [PASS] 4. Security Hardening Headers (nosniff, DENY present)")
            passed += 1
        else:
            print(f"  [FAIL] 4. Security headers missing: {dict(headers)}")
    except Exception as exc:
        print(f"  [FAIL] 4. Security headers check failed: {exc}")

    # Check 5: Agent Catalog Registry
    try:
        res = client.get("/api/v1/agents")
        if res.status_code == 200:
            agents = res.json().get("items", [])
            print(f"  [PASS] 5. Agent Registry Availability ({len(agents)} agents loaded)")
            passed += 1
        else:
            print(f"  [FAIL] 5. Agent registry returned HTTP {res.status_code}")
    except Exception as exc:
        print(f"  [FAIL] 5. Agent registry check failed: {exc}")

    # Check 6: Workflow API Reachability
    try:
        res = client.get("/api/v1/workflows")
        if res.status_code == 200:
            print("  [PASS] 6. Workflow API Reachability (GET /api/v1/workflows)")
            passed += 1
        else:
            print(f"  [FAIL] 6. Workflow API returned HTTP {res.status_code}")
    except Exception as exc:
        print(f"  [FAIL] 6. Workflow API check failed: {exc}")

    # Check 7: Structured JSON Telemetry Snapshot
    try:
        res = client.get("/api/v1/telemetry")
        if res.status_code == 200 and "counters" in res.json():
            print("  [PASS] 7. Structured JSON Telemetry (GET /api/v1/telemetry)")
            passed += 1
        else:
            print(f"  [FAIL] 7. Telemetry endpoint returned HTTP {res.status_code}")
    except Exception as exc:
        print(f"  [FAIL] 7. Telemetry check failed: {exc}")

    # Check 8: Prometheus/OpenMetrics Exposition
    try:
        res = client.get("/api/v1/metrics")
        if res.status_code == 200 and "text/plain" in res.headers.get("content-type", ""):
            print("  [PASS] 8. Prometheus / OpenMetrics Exposition (GET /api/v1/metrics)")
            passed += 1
        else:
            print(f"  [FAIL] 8. Metrics exposition returned HTTP {res.status_code}")
    except Exception as exc:
        print(f"  [FAIL] 8. Metrics exposition check failed: {exc}")

    # Check 9: Standardized Error Envelope
    try:
        res = client.get("/api/v1/workflows/non-existent-wf-id-999")
        if res.status_code == 404:
            body = res.json()
            if "error" in body and "code" in body["error"]:
                print("  [PASS] 9. Error Envelope Sanitization (404 structured response)")
                passed += 1
            else:
                print(f"  [FAIL] 9. 404 response missing standardized error envelope")
        else:
            print(f"  [FAIL] 9. Non-existent workflow returned unexpected status HTTP {res.status_code}")
    except Exception as exc:
        print(f"  [FAIL] 9. Error envelope check failed: {exc}")

    # Check 10: Request Size Limit Guard (Rejection of oversized payload > 10MB)
    try:
        oversized_payload = b"x" * (10 * 1024 * 1024 + 1024)
        res = client.post(
            "/api/v1/workflows",
            content=oversized_payload,
            headers={"Content-Type": "application/json"},
        )
        if res.status_code == 413:
            print("  [PASS] 10. Request Body Size Limiter (413 Payload Too Large on >10MB payload)")
            passed += 1
        else:
            print(f"  [FAIL] 10. Request size limit guard returned status HTTP {res.status_code} instead of 413")
    except Exception as exc:
        print(f"  [FAIL] 10. Request size limit guard failed: {exc}")

    print(f"\n==================================================")
    print(f"SMOKE TEST SUMMARY: {passed}/{total} checks passed")
    print(f"==================================================\n")

    return passed == total


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smoke test Multi-Agent Workflow Orchestrator API")
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000",
        help="Base URL of deployed API (default: http://127.0.0.1:8000)",
    )
    args = parser.parse_args()

    success = run_smoke_tests(args.url)
    sys.exit(0 if success else 1)
