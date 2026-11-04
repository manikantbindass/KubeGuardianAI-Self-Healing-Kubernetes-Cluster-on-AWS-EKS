"""Actual HTTP smoke/load test against a running detector; only synthetic data is submitted."""

import argparse
import json
import os
import statistics
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))
from kubesentinel_ml.dataset import synthetic  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8010")
    parser.add_argument("--expected-mode", choices=["trained", "rules_fallback"], default="trained")
    parser.add_argument("--output", type=Path, default=Path(".cache/ml/http-load.json"))
    args = parser.parse_args()
    auth = os.environ.get("DETECTOR_API_TOKEN", "")

    def request(path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        req = urllib.request.Request(
            args.url + path,
            data=json.dumps(payload).encode() if payload else None,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {auth}"},
        )
        with urllib.request.urlopen(req, timeout=20) as response:
            body: dict[str, Any] = json.load(response)
            return body

    assert request("/health")["status"] == "ok"
    ready = request("/ready")
    assert ready["mode"] == args.expected_mode, ready
    payload = {
        "observations": [r.model_dump(mode="json") for r in synthetic(minutes=300)[100:108]],
        "detector": "isolation_forest",
    }

    def score(_: int) -> float:
        started = time.perf_counter()
        result = request("/api/v1/score", payload)
        assert result["mode"] == args.expected_mode
        assert len(result["windows"]) == 4
        assert all(w["provenance"] == "synthetic" for w in result["windows"])
        assert any(w["score"]["anomalous"] for w in result["windows"])
        return (time.perf_counter() - started) * 1000

    with ThreadPoolExecutor(max_workers=4) as pool:
        latencies = list(pool.map(score, range(40)))
    report = {
        "requests": 40,
        "concurrency": 4,
        "windows_per_request": 4,
        "provenance": "synthetic",
        "mode": args.expected_mode,
        "http_latency_ms": {"p50": statistics.median(latencies), "p95": sorted(latencies)[37]},
        "drift": request("/api/v1/drift"),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
