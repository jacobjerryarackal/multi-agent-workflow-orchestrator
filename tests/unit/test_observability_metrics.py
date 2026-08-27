"""Unit tests for Phase 7.3 structured telemetry, metrics collector, and middleware."""

import pytest
from app.core.telemetry import MetricsCollector


def test_metrics_collector_counter():
    collector = MetricsCollector()
    collector.increment_counter("test_counter", 1.0, {"route": "/test", "method": "GET"})
    collector.increment_counter("test_counter", 2.0, {"route": "/test", "method": "GET"})

    snapshot = collector.to_dict()
    assert "test_counter" in snapshot["counters"]
    assert len(snapshot["counters"]["test_counter"]) == 1
    assert snapshot["counters"]["test_counter"][0]["value"] == 3.0
    assert snapshot["counters"]["test_counter"][0]["labels"] == {"route": "/test", "method": "GET"}


def test_metrics_collector_gauge():
    collector = MetricsCollector()
    collector.set_gauge("test_gauge", 10.0, {"component": "pool"})
    collector.increment_gauge("test_gauge", 5.0, {"component": "pool"})
    collector.decrement_gauge("test_gauge", 2.0, {"component": "pool"})

    snapshot = collector.to_dict()
    assert "test_gauge" in snapshot["gauges"]
    assert snapshot["gauges"]["test_gauge"][0]["value"] == 13.0


def test_metrics_collector_histogram():
    collector = MetricsCollector()
    collector.observe_histogram("test_latency", 0.05, {"route": "/health"})
    collector.observe_histogram("test_latency", 0.15, {"route": "/health"})

    snapshot = collector.to_dict()
    assert "test_latency" in snapshot["histograms"]
    entry = snapshot["histograms"]["test_latency"][0]
    assert entry["count"] == 2
    assert entry["sum"] == pytest.approx(0.20)
    assert entry["buckets"][0.1] == 1
    assert entry["buckets"][0.25] == 2


def test_metrics_collector_label_sanitization():
    collector = MetricsCollector()
    # Attempting to supply high-cardinality keys must be safely dropped or blocked
    collector.increment_counter(
        "test_cardinality",
        1.0,
        {
            "route": "/api/v1/workflows",
            "workflow_id": "wf-secret-12345",
            "execution_id": "exec-9999",
            "prompt": "Sensitive text content",
        },
    )

    snapshot = collector.to_dict()
    labels = snapshot["counters"]["test_cardinality"][0]["labels"]
    assert labels == {"route": "/api/v1/workflows"}
    assert "workflow_id" not in labels
    assert "execution_id" not in labels
    assert "prompt" not in labels


def test_prometheus_exposition_format():
    collector = MetricsCollector()
    collector.increment_counter("http_requests_total", 5.0, {"method": "GET", "status_code": "200"})
    collector.set_gauge("database_pool_size", 5.0)
    collector.observe_histogram("http_request_duration_seconds", 0.02, {"route": "/health"})

    prom_text = collector.to_prometheus_text()
    assert "# HELP http_requests_total" in prom_text
    assert "# TYPE http_requests_total counter" in prom_text
    assert 'http_requests_total{method="GET",status_code="200"} 5.0' in prom_text

    assert "# HELP database_pool_size" in prom_text
    assert "# TYPE database_pool_size gauge" in prom_text
    assert "database_pool_size 5.0" in prom_text

    assert "# HELP http_request_duration_seconds" in prom_text
    assert "# TYPE http_request_duration_seconds histogram" in prom_text
    assert 'http_request_duration_seconds_count{route="/health"} 1' in prom_text
    assert 'http_request_duration_seconds_bucket{' in prom_text
    assert 'le="+Inf"' in prom_text
    assert 'route="/health"' in prom_text
