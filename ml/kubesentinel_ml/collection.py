"""Read-only, namespace-aggregate export. Never retain raw log messages or event text."""

import hashlib
import json
import subprocess
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from typing import Any

from kubesentinel_ml.schema import Metrics, Observation

NS = 'namespace="kubesentinel"'
QUERIES = {
    "cpu_ratio": f'sum(rate(container_cpu_usage_seconds_total{{{NS},container!=""}}[2m])) / '
    f'(sum(kube_pod_container_resource_requests{{{NS},resource="cpu"}}) > 0)',
    "memory_ratio": f'sum(container_memory_working_set_bytes{{{NS},container!=""}}) / '
    f'(sum(kube_pod_container_resource_limits{{{NS},resource="memory"}}) > 0)',
    "restarts": f"sum(increase(kube_pod_container_status_restarts_total{{{NS}}}[30s]))",
    "error_ratio": '(sum(rate(sentinel_http_requests_total{status=~"5.."}[2m])) or vector(0)) / '
    "(sum(rate(sentinel_http_requests_total[2m])) > 0)",
    "latency_p95_ms": "1000 * histogram_quantile(0.95, sum by(le) "
    "(rate(sentinel_http_duration_seconds_bucket[2m])))",
    "pending_seconds": f"max((time() - kube_pod_created{{{NS}}}) and on(namespace,pod) "
    f'(kube_pod_status_phase{{{NS},phase="Pending"}} == 1)) '
    f"or (0 * sum(kube_pod_status_phase{{{NS}}}))",
    "availability_ratio": f"sum(kube_deployment_status_replicas_available{{{NS}}}) / "
    f"(sum(kube_deployment_spec_replicas{{{NS}}}) > 0)",
    "deployment_changes": f"sum(changes(kube_deployment_metadata_generation{{{NS}}}[30s]))",
    "node_pressure_ratio": "max(kube_node_status_condition{condition=~"
    '"MemoryPressure|DiskPressure|PIDPressure",status="true"})',
    "saturation_ratio": 'sum(kube_pod_container_resource_requests{resource="cpu"}) / '
    '(sum(kube_node_status_allocatable{resource="cpu"}) > 0)',
}


def get_json(base: str, path: str, params: dict[str, str]) -> dict[str, Any]:
    parsed = urllib.parse.urlsplit(base)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
        raise ValueError("Expected an operator-configured HTTP(S) endpoint without credentials")
    url = base.rstrip("/") + path + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=5) as response:
        raw = response.read(4_000_001)
    if len(raw) > 4_000_000:
        raise ValueError("Telemetry response exceeds limit")
    body: dict[str, Any] = json.loads(raw)
    if body.get("status") != "success":
        raise ValueError("Telemetry source returned an error")
    return body


def collect(
    prometheus: str,
    loki: str,
    start: datetime,
    end: datetime,
    dataset_id: str,
    kube_context: str | None = None,
) -> tuple[list[Observation], dict[str, Any]]:
    if (
        start.tzinfo is None
        or end.tzinfo is None
        or not 60 <= (end - start).total_seconds() <= 21600
    ):
        raise ValueError("Collection requires timezone-aware start/end, duration 1 minute..6 hours")
    collected_at = datetime.now(UTC).isoformat()
    points: dict[float, dict[str, float | None]] = {}
    errors: list[str] = []
    for key, query in QUERIES.items():
        try:
            body = get_json(
                prometheus,
                "/api/v1/query_range",
                {
                    "query": query,
                    "start": str(start.timestamp()),
                    "end": str(end.timestamp()),
                    "step": "30",
                },
            )
            for series in body["data"]["result"]:
                for timestamp, value in series.get("values", []):
                    number = float(value)
                    if number != number or abs(number) == float("inf"):
                        continue
                    points.setdefault(float(timestamp), {})[key] = number
        except (OSError, ValueError, KeyError, TypeError):
            errors.append(key)
    rows = []
    for timestamp, values in sorted(points.items()):
        # p95 NaN/no requests remains missing. No fabricated zero-fill during outages.
        rows.append(
            Observation(
                id=hashlib.sha256(f"{dataset_id}:prometheus:{timestamp}".encode()).hexdigest(),
                timestamp=datetime.fromtimestamp(timestamp, UTC),
                dataset_id=dataset_id,
                provenance="real",
                origin="prometheus",
                resource="namespace/kubesentinel",
                metrics=Metrics.model_validate(values),
            )
        )
    try:
        body = get_json(
            loki,
            "/loki/api/v1/query_range",
            {
                "query": (
                    'sum(count_over_time({service_name="sentinel-api"}'
                    ' | json | level="ERROR" [30s])) or '
                    '(0 * sum(count_over_time({service_name="sentinel-api"}[30s])))'
                ),
                "start": str(int(start.timestamp() * 1e9)),
                "end": str(int(end.timestamp() * 1e9)),
                "step": "30",
            },
        )
        for series in body["data"]["result"]:
            for timestamp, value in series.get("values", []):
                # Range counts describe the interval ending at this instant.
                stamp = float(timestamp) - 0.000001
                rows.append(
                    Observation(
                        id=hashlib.sha256(f"{dataset_id}:loki:{timestamp}".encode()).hexdigest(),
                        timestamp=datetime.fromtimestamp(stamp, UTC),
                        dataset_id=dataset_id,
                        provenance="real",
                        origin="loki",
                        resource="namespace/kubesentinel",
                        metrics=Metrics(log_errors=float(value)),
                    )
                )
    except (OSError, ValueError, KeyError, TypeError):
        errors.append("log_errors")
    if kube_context:
        result = subprocess.run(
            [
                "kubectl",
                "--context",
                kube_context,
                "get",
                "events",
                "-n",
                "kubesentinel",
                "-o",
                "json",
            ],
            capture_output=True,
            timeout=15,
            check=True,
        )
        if len(result.stdout) > 4_000_000:
            raise ValueError("Event snapshot exceeds limit")
        for event in json.loads(result.stdout).get("items", []):
            timestamp = event.get("series", {}).get("lastObservedTime") or event.get(
                "lastTimestamp"
            )
            if event.get("type") != "Warning" or not timestamp:
                continue
            observed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if start <= observed <= end:
                rows.append(
                    Observation(
                        id=hashlib.sha256(
                            f"{dataset_id}:event:{event['metadata']['uid']}".encode()
                        ).hexdigest(),
                        timestamp=observed,
                        dataset_id=dataset_id,
                        provenance="real",
                        origin="kubernetes",
                        resource="namespace/kubesentinel",
                        metrics=Metrics(warning_events=1),
                    )
                )
    if not rows:
        raise ValueError("No real telemetry returned; do not substitute synthetic data")
    return rows, {
        "collected_at": collected_at,
        "dataset_id": dataset_id,
        "provenance": "real",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "step_seconds": 30,
        "queries": QUERIES,
        "unavailable_metrics": errors,
        "events_requested": bool(kube_context),
        "labels": "unknown, not healthy by default",
        "event_semantics": "one Warning per retained event UID; best-effort snapshot",
    }
