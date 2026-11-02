"""Real kind telemetry acceptance. Creates one memory-limited, scoped OOM fixture."""

import json
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = "kind-kubesentinel"


def kube(*args: str, payload: dict[str, Any] | None = None) -> str:
    return subprocess.run(
        ["kubectl", "--context", CONTEXT, "-n", "kubesentinel", *args],
        cwd=ROOT,
        input=json.dumps(payload) if payload else None,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def request(url: str, payload: dict[str, Any] | None = None, method: str | None = None) -> Any:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.load(response)


def wait_for(check: Any, description: str, timeout: int = 180) -> Any:
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        try:
            value = check()
            if value:
                print("PASS:", description, flush=True)
                return value
        except (OSError, ValueError, KeyError, AssertionError) as error:
            last = type(error).__name__
        time.sleep(3)
    raise AssertionError(f"Timed out: {description} ({last})")


def query(expression: str) -> list[dict[str, Any]]:
    body = request(
        "http://127.0.0.1:9090/api/v1/query?" + urllib.parse.urlencode({"query": expression})
    )
    assert body["status"] == "success"
    rows: list[dict[str, Any]] = body["data"]["result"]
    return rows


def incidents() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = request("http://127.0.0.1:8100/api/v1/incidents?limit=100")
    return rows


def main() -> None:
    evidence = ROOT / ".cache" / "observability"
    evidence.mkdir(parents=True, exist_ok=True)
    ports = {
        "prometheus": (9090, 9090),
        "grafana": (3300, 3000),
        "loki": (3100, 3100),
        "alertmanager": (9093, 9093),
        "sentinel-api": (8100, 8000),
        "sentinel-dashboard": (3200, 3000),
    }
    processes = []
    handles = []
    try:
        for service, (host, port) in ports.items():
            handle = (evidence / f"{service}-forward.log").open("w")
            handles.append(handle)
            processes.append(
                subprocess.Popen(
                    [
                        "kubectl",
                        "--context",
                        CONTEXT,
                        "-n",
                        "kubesentinel",
                        "port-forward",
                        f"service/{service}",
                        f"{host}:{port}",
                    ],
                    stdout=handle,
                    stderr=handle,
                )
            )
        wait_for(lambda: request("http://127.0.0.1:8100/api/v1/health"), "live API")
        for _ in range(40):
            request("http://127.0.0.1:8100/api/v1/version")
            time.sleep(0.1)
        kube(
            "exec",
            "deployment/prometheus",
            "--",
            "promtool",
            "check",
            "rules",
            "/etc/prometheus/rules.yml",
        )
        wait_for(
            lambda: query('up{job="sentinel-api"}')[0]["value"][1] == "1", "API metrics scrape"
        )
        wait_for(lambda: query('kube_node_status_capacity{resource="cpu"}'), "real node capacity")
        wait_for(
            lambda: query(
                'container_memory_working_set_bytes{namespace="kubesentinel",container!=""}'
            ),
            "real cAdvisor memory",
        )
        wait_for(
            lambda: query(
                'sum(rate(container_cpu_usage_seconds_total{namespace="kubesentinel",container!=""}[2m]))'
            ),
            "real CPU usage",
        )
        wait_for(
            lambda: query("sum(otelcol_receiver_accepted_spans)")[0]["value"][1] != "0",
            "OTLP trace reception",
        )
        logs_query = urllib.parse.urlencode({"query": '{service_name="sentinel-api"}', "limit": 50})
        logs = wait_for(
            lambda: request("http://127.0.0.1:3100/loki/api/v1/query_range?" + logs_query)["data"][
                "result"
            ],
            "API JSON logs in Loki",
        )
        (evidence / "loki.json").write_text(json.dumps(logs), encoding="utf-8")
        assert any('"trace_id":' in value[1] for stream in logs for value in stream["values"])
        now = datetime.now(UTC)
        silence = request(
            "http://127.0.0.1:9093/api/v2/silences",
            {
                "matchers": [
                    {"name": "alertname", "value": "WorkloadReplicasUnavailable", "isRegex": False},
                    {"name": "deployment", "value": "sentinel-fault", "isRegex": False},
                ],
                "startsAt": now.isoformat(),
                "endsAt": (now + timedelta(minutes=10)).isoformat(),
                "createdBy": "kind-acceptance",
                "comment": "Controlled fault silence test",
            },
        )
        fixture = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": "sentinel-fault"},
            "spec": {
                "replicas": 1,
                "selector": {"matchLabels": {"test": "sentinel-fault"}},
                "template": {
                    "metadata": {"labels": {"test": "sentinel-fault"}},
                    "spec": {
                        "automountServiceAccountToken": False,
                        "containers": [
                            {
                                "name": "fault",
                                "image": "kubesentinel/api:phase04",
                                "command": [
                                    "python",
                                    "-c",
                                    "import time; time.sleep(3); "
                                    "bytearray(256*1024*1024); time.sleep(30)",
                                ],
                                "resources": {
                                    "requests": {"cpu": "10m", "memory": "32Mi"},
                                    "limits": {"cpu": "100m", "memory": "32Mi"},
                                },
                            }
                        ],
                    },
                },
            },
        }
        existing = kube("get", "deployment", "sentinel-fault", "--ignore-not-found", "-o", "name")
        assert not existing, "Refusing to replace a pre-existing fault workload"
        kube("apply", "-f", "-", payload=fixture)
        wait_for(
            lambda: query(
                "kube_pod_container_status_last_terminated_reason"
                '{namespace="kubesentinel",reason="OOMKilled"} == 1'
            ),
            "real controlled OOMKilled metric",
        )
        wait_for(
            lambda: any(
                row["source"] == "kubernetes" and row["resource"].startswith("sentinel-fault")
                for row in incidents()
            ),
            "genuine Kubernetes Warning becomes durable incident",
        )
        wait_for(
            lambda: any(
                alert["labels"].get("deployment") == "sentinel-fault"
                and alert["labels"].get("alertname") == "WorkloadReplicasUnavailable"
                and alert["status"]["silencedBy"]
                for alert in request("http://127.0.0.1:9093/api/v2/alerts")
            ),
            "Alertmanager silence applies to genuine alert",
        )
        assert not any(
            row["source"] == "alertmanager"
            and row["reason"] == "WorkloadReplicasUnavailable"
            and row["resource"] == "sentinel-fault"
            for row in incidents()
        )
        request("http://127.0.0.1:9093/api/v2/silence/" + silence["silenceID"], method="DELETE")
        wait_for(
            lambda: any(
                row["source"] == "alertmanager" and row["resource"] == "sentinel-fault"
                for row in incidents()
            ),
            "unsilenced real alert creates incident",
        )
        before = incidents()
        (evidence / "incidents.json").write_text(json.dumps(before), encoding="utf-8")
        kube("delete", "deployment", "sentinel-fault", "--wait=true")
        wait_for(
            lambda: any(
                row["source"] == "alertmanager"
                and row["resource"] == "sentinel-fault"
                and row["status"] == "resolved"
                for row in incidents()
            ),
            "resolved alert updates existing incident",
        )
        # Capture genuine Grafana panels while stores and Prometheus are healthy.
        subprocess.run(
            ["node", "scripts/capture-observability.mjs"], cwd=ROOT, check=True, timeout=180
        )
        kube("scale", "deployment/prometheus", "--replicas=0")

        def metrics_down() -> bool:
            try:
                request("http://127.0.0.1:8100/api/v1/metrics/cpu")
            except urllib.error.HTTPError as error:
                return error.code == 503
            return False

        try:
            wait_for(metrics_down, "Prometheus outage returns bounded 503")
            assert incidents(), "Persistent incidents must remain readable during metrics outage"
            assert request("http://127.0.0.1:8100/api/v1/health")["status"] == "ok"
        finally:
            kube("scale", "deployment/prometheus", "--replicas=1")
        kube("rollout", "status", "deployment/prometheus", "--timeout=180s")
        print("PASS: end-to-end observability acceptance", flush=True)
    finally:
        kube("delete", "deployment", "sentinel-fault", "--ignore-not-found")
        for process in processes:
            process.terminate()
            process.wait(timeout=10)
        for handle in handles:
            handle.close()


if __name__ == "__main__":
    main()
