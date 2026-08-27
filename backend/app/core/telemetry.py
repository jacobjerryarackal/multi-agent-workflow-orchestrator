"""
In-process, thread-safe structured metrics collector and OpenMetrics/Prometheus exporter.

NOTE ON MULTI-WORKER / PROCESS-LOCAL ARCHITECTURE:
This MetricsCollector is an in-memory, process-local singleton. It provides real-time
low-latency operational telemetry without external dependencies (e.g. Prometheus pushgateway,
Redis, Datadog).
Limitations:
1. Metrics reset when the backend process restarts.
2. In multi-worker deployments (e.g. Uvicorn with multiple workers), metrics are isolated
   to each worker process and not globally aggregated in-process.
"""

from collections import defaultdict
import math
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple


class MetricsCollector:
    """
    Thread-safe in-memory metric store supporting Counters, Gauges, and Histograms.
    Enforces strict low-cardinality label filtering and outputs Prometheus/OpenMetrics text format.
    """

    _instance: Optional["MetricsCollector"] = None
    _lock = threading.Lock()

    # Allowed Prometheus label keys
    ALLOWED_LABEL_KEYS = {
        "method",
        "route",
        "status_code",
        "agent_id",
        "model",
        "provider",
        "error_category",
        "error_type",
        "verdict",
        "trigger_type",
        "worker_id",
        "reason",
        "token_type",
        "evaluator_type",
        "artifact_type",
        "status",
        "le",
    }

    # Forbidden high-cardinality keys
    FORBIDDEN_LABEL_KEYS = {
        "workflow_id",
        "execution_id",
        "task_id",
        "correlation_id",
        "user_id",
        "prompt",
        "payload",
        "url",
        "raw_url",
    }

    # Default histogram buckets for latency (in seconds)
    DEFAULT_DURATION_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)

    def __init__(self):
        self._counters: Dict[str, Dict[Tuple[Tuple[str, str], ...], float]] = defaultdict(lambda: defaultdict(float))
        self._gauges: Dict[str, Dict[Tuple[Tuple[str, str], ...], float]] = defaultdict(lambda: defaultdict(float))
        self._histograms: Dict[str, Dict[Tuple[Tuple[str, str], ...], Dict[str, Any]]] = defaultdict(dict)
        self._descriptions: Dict[str, str] = {}
        self._metric_types: Dict[str, str] = {}
        self._mutex = threading.RLock()
        self._register_default_metadata()

    @classmethod
    def get_instance(cls) -> "MetricsCollector":
        """Singleton accessor."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing)."""
        with cls._lock:
            cls._instance = cls()

    def _sanitize_labels(self, labels: Optional[Dict[str, Any]]) -> Tuple[Tuple[str, str], ...]:
        """Validates and sanitizes label key/values to strictly low-cardinality allowed set."""
        if not labels:
            return ()
        clean: List[Tuple[str, str]] = []
        for k, v in sorted(labels.items()):
            k_clean = str(k).strip()
            if k_clean in self.FORBIDDEN_LABEL_KEYS:
                continue
            if k_clean not in self.ALLOWED_LABEL_KEYS:
                continue
            v_clean = str(v).strip()
            # Truncate label value length to prevent runaway memory
            if len(v_clean) > 64:
                v_clean = v_clean[:64]
            clean.append((k_clean, v_clean))
        return tuple(clean)

    def _register_default_metadata(self) -> None:
        """Registers standard OpenMetrics descriptions and types."""
        self._descriptions = {
            # HTTP metrics
            "http_requests_total": "Total count of HTTP requests received",
            "http_request_duration_seconds": "HTTP request duration in seconds",
            "http_errors_total": "Total count of HTTP request errors",
            # Workflow metrics
            "workflow_submissions_total": "Total count of submitted workflow execution requests",
            "workflow_started_total": "Total count of workflow executions transitioned to RUNNING",
            "workflow_completed_total": "Total count of successfully completed workflow executions",
            "workflow_failed_total": "Total count of failed workflow executions",
            "workflow_cancelled_total": "Total count of cancelled workflow executions",
            "workflow_duration_seconds": "Workflow execution total duration in seconds",
            # Task metrics
            "task_started_total": "Total count of task execution attempts started",
            "task_completed_total": "Total count of successfully completed task executions",
            "task_failed_total": "Total count of failed task executions",
            "task_retry_total": "Total count of task retries dispatched",
            "task_timeout_total": "Total count of task execution timeouts",
            "task_execution_duration_seconds": "Task execution duration in seconds",
            "task_queue_wait_seconds": "Time task spent waiting in READY state before dispatch",
            # Lease & Recovery metrics
            "task_lease_claim_total": "Total count of task leases claimed by workers",
            "task_lease_renewal_total": "Total count of task lease heartbeat renewals",
            "task_lease_expired_total": "Total count of expired task leases detected by watchdog",
            "task_recovery_total": "Total count of task lease recoveries performed",
            "task_recovery_retry_total": "Total count of recovered tasks requeued for retry",
            "task_recovery_failure_total": "Total count of recovered tasks transitioned to terminal failure",
            # Background manager metrics
            "background_active_executions": "Current number of in-process active workflow execution tasks",
            "background_dispatch_total": "Total count of background execution tasks dispatched",
            "background_dispatch_failures_total": "Total count of background execution dispatch failures",
            "background_watchdog_sweeps_total": "Total count of watchdog recovery sweeps executed",
            "background_tasks_recovered_total": "Total count of tasks successfully recovered by watchdog",
            "background_shutdowns_total": "Total count of background manager shutdown events",
            # Model provider metrics
            "model_requests_total": "Total count of LLM provider API requests",
            "model_request_duration_seconds": "LLM provider API request latency in seconds",
            "model_request_failures_total": "Total count of LLM provider API request failures",
            "model_timeout_total": "Total count of LLM provider API timeouts",
            "model_tokens_total": "Total count of tokens consumed across LLM requests",
            # Evaluation metrics
            "evaluation_started_total": "Total count of evaluation passes started",
            "evaluation_completed_total": "Total count of evaluation passes completed by verdict",
            "evaluation_duration_seconds": "Evaluation pipeline execution duration in seconds",
            "evaluation_score": "Quality evaluation score histogram",
            # Approval metrics
            "approval_requested_total": "Total count of approval gates requested",
            "approval_approved_total": "Total count of approval gates approved",
            "approval_rejected_total": "Total count of approval gates rejected",
            "approval_escalated_total": "Total count of approval gates escalated",
            "approval_wait_duration_seconds": "Time spent waiting for human approval decision",
            # Artifact metrics
            "artifact_created_total": "Total count of artifacts created and stored",
            "artifact_integrity_verified_total": "Total count of artifact SHA-256 integrity verifications",
            "artifact_integrity_failure_total": "Total count of artifact SHA-256 integrity failures",
            # Database pool metrics
            "database_connections_checked_out": "Current number of active connections checked out from pool",
            "database_pool_size": "Configured database connection pool size",
            "database_pool_overflow": "Current overflow connections in database connection pool",
            "database_connection_failures": "Total count of database connection acquisition failures",
        }
        for name in self._descriptions:
            if "duration_seconds" in name or "wait_seconds" in name or name == "evaluation_score":
                self._metric_types[name] = "histogram"
            elif name in ("background_active_executions", "database_connections_checked_out", "database_pool_size", "database_pool_overflow"):
                self._metric_types[name] = "gauge"
            else:
                self._metric_types[name] = "counter"

    # --- Instrumentation API ---

    def increment_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, Any]] = None) -> None:
        """Increments a monotonic counter metric."""
        if value < 0:
            return
        sanitized = self._sanitize_labels(labels)
        with self._mutex:
            self._counters[name][sanitized] += value
            if name not in self._metric_types:
                self._metric_types[name] = "counter"

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, Any]] = None) -> None:
        """Sets an instantaneous gauge value."""
        sanitized = self._sanitize_labels(labels)
        with self._mutex:
            self._gauges[name][sanitized] = float(value)
            if name not in self._metric_types:
                self._metric_types[name] = "gauge"

    def increment_gauge(self, name: str, value: float = 1.0, labels: Optional[Dict[str, Any]] = None) -> None:
        """Increments a gauge value."""
        sanitized = self._sanitize_labels(labels)
        with self._mutex:
            self._gauges[name][sanitized] += float(value)
            if name not in self._metric_types:
                self._metric_types[name] = "gauge"

    def decrement_gauge(self, name: str, value: float = 1.0, labels: Optional[Dict[str, Any]] = None) -> None:
        """Decrements a gauge value."""
        sanitized = self._sanitize_labels(labels)
        with self._mutex:
            self._gauges[name][sanitized] -= float(value)
            if name not in self._metric_types:
                self._metric_types[name] = "gauge"

    def observe_histogram(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, Any]] = None,
        buckets: Tuple[float, ...] = DEFAULT_DURATION_BUCKETS,
    ) -> None:
        """Observes a value in a histogram metric."""
        sanitized = self._sanitize_labels(labels)
        with self._mutex:
            if sanitized not in self._histograms[name]:
                self._histograms[name][sanitized] = {
                    "count": 0,
                    "sum": 0.0,
                    "buckets": {b: 0 for b in buckets},
                }
            hist = self._histograms[name][sanitized]
            hist["count"] += 1
            hist["sum"] += float(value)
            for b in sorted(hist["buckets"].keys()):
                if value <= b:
                    hist["buckets"][b] += 1
            if name not in self._metric_types:
                self._metric_types[name] = "histogram"

    # --- Export API ---

    def to_dict(self) -> Dict[str, Any]:
        """Returns JSON-serializable snapshot of all metrics."""
        with self._mutex:
            counters_dict: Dict[str, List[Dict[str, Any]]] = {}
            for name, entries in self._counters.items():
                counters_dict[name] = [
                    {"labels": dict(lbls), "value": val} for lbls, val in entries.items()
                ]

            gauges_dict: Dict[str, List[Dict[str, Any]]] = {}
            for name, entries in self._gauges.items():
                gauges_dict[name] = [
                    {"labels": dict(lbls), "value": val} for lbls, val in entries.items()
                ]

            histograms_dict: Dict[str, List[Dict[str, Any]]] = {}
            for name, entries in self._histograms.items():
                histograms_dict[name] = [
                    {
                        "labels": dict(lbls),
                        "count": data["count"],
                        "sum": round(data["sum"], 6),
                        "buckets": data["buckets"],
                    }
                    for lbls, data in entries.items()
                ]

            return {
                "timestamp": time.time(),
                "counters": counters_dict,
                "gauges": gauges_dict,
                "histograms": histograms_dict,
            }

    def to_prometheus_text(self) -> str:
        """Generates OpenMetrics / Prometheus standard exposition plain text format."""
        lines: List[str] = []
        with self._mutex:
            # Collect all distinct metric names
            all_metric_names = sorted(
                set(list(self._counters.keys()) + list(self._gauges.keys()) + list(self._histograms.keys()))
            )

            for name in all_metric_names:
                desc = self._descriptions.get(name, f"Application metric {name}")
                mtype = self._metric_types.get(name, "untyped")
                lines.append(f"# HELP {name} {desc}")
                lines.append(f"# TYPE {name} {mtype}")

                if name in self._counters:
                    for lbls, val in sorted(self._counters[name].items()):
                        lbl_str = self._format_label_str(lbls)
                        lines.append(f"{name}{lbl_str} {val}")

                if name in self._gauges:
                    for lbls, val in sorted(self._gauges[name].items()):
                        lbl_str = self._format_label_str(lbls)
                        lines.append(f"{name}{lbl_str} {val}")

                if name in self._histograms:
                    for lbls, data in sorted(self._histograms[name].items()):
                        # Bucket lines
                        for b_val, count in sorted(data["buckets"].items()):
                            b_lbls = list(lbls) + [("le", str(b_val))]
                            lines.append(f"{name}_bucket{self._format_label_str(b_lbls)} {count}")
                        # +Inf bucket line
                        inf_lbls = list(lbls) + [("le", "+Inf")]
                        lines.append(f"{name}_bucket{self._format_label_str(inf_lbls)} {data['count']}")
                        # Sum and Count
                        base_lbl_str = self._format_label_str(lbls)
                        lines.append(f"{name}_sum{base_lbl_str} {round(data['sum'], 6)}")
                        lines.append(f"{name}_count{base_lbl_str} {data['count']}")

                lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _format_label_str(labels: Any) -> str:
        """Formats tuple or list of key-value pairs into '{k="v", ...}'."""
        if not labels:
            return ""
        items = []
        for k, v in sorted(labels):
            # Escape quotes and backslashes in label values
            v_escaped = str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            items.append(f'{k}="{v_escaped}"')
        return "{" + ",".join(items) + "}"


# Global convenience helper
telemetry = MetricsCollector.get_instance()
