"""Bounded loopback HTTP benchmark; raw observations, never production claims."""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def request(url: str) -> tuple[float, int]:
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            response.read(1048576)
            status = response.status
    except OSError:
        status = 0
    return (time.perf_counter() - start) * 1000, status


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-api", action="store_true")
    parser.add_argument("--url", default="http://127.0.0.1:18090/api/v1/health")
    parser.add_argument("--output", type=Path, default=Path(".cache/benchmarks/http"))
    args = parser.parse_args()
    if urlparse(args.url).hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Only loopback targets are authorized by this harness")
    args.output.mkdir(parents=True, exist_ok=True)
    process = None
    with (args.output / "server.log").open("w", encoding="utf-8") as log:
        try:
            if args.start_api:
                if args.url != "http://127.0.0.1:18090/api/v1/health":
                    raise ValueError("Managed server uses the fixed isolated benchmark port")
                environment = {**os.environ, "PYTHONPATH": "apps/api"}
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "kubesentinel_api.main:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        "18090",
                        "--no-access-log",
                    ],
                    env=environment,
                    stdout=log,
                    stderr=log,
                )
                for _ in range(50):
                    if process.poll() is not None:
                        raise RuntimeError("Benchmark API exited")
                    if request(args.url)[1] == 200:
                        break
                    time.sleep(0.1)
                else:
                    raise RuntimeError("Benchmark API did not start")
            rows: list[dict[str, Any]] = []
            summaries = []
            for concurrency in (1, 4, 8):
                for repetition in range(3):
                    start = time.perf_counter()
                    with ThreadPoolExecutor(max_workers=concurrency) as pool:
                        observations = list(pool.map(request, [args.url] * 100))
                    elapsed = time.perf_counter() - start
                    values = sorted(latency for latency, _ in observations)
                    errors = sum(status != 200 for _, status in observations)
                    summaries.append(
                        {
                            "concurrency": concurrency,
                            "repetition": repetition,
                            "requests": 100,
                            "duration_seconds": elapsed,
                            "requests_per_second": 100 / elapsed,
                            "error_rate": errors / 100,
                            **{
                                f"p{p}_ms": values[min(99, int(p / 100 * 100) - 1)]
                                for p in (50, 95, 99)
                            },
                        }
                    )
                    rows.extend(
                        {
                            "concurrency": concurrency,
                            "repetition": repetition,
                            "latency_ms": latency,
                            "status": status,
                        }
                        for latency, status in observations
                    )
            with (args.output / "raw.csv").open("w", newline="", encoding="utf-8") as output:
                writer = csv.DictWriter(output, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            result = {
                "kind": "loopback-health-only",
                "platform": platform.platform(),
                "python": platform.python_version(),
                "url": args.url,
                "source_commit": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], text=True
                ).strip(),
                "working_tree_changes": bool(
                    subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
                ),
                "database_exercised": False,
                "cluster_exercised": False,
                "summaries": summaries,
            }
            (args.output / "summary.json").write_text(
                json.dumps(result, indent=2) + "\n", encoding="utf-8"
            )
            print(json.dumps(summaries, indent=2))
            if any(row["error_rate"] for row in summaries):
                raise SystemExit(1)
        finally:
            if process:
                process.terminate()
                process.wait(timeout=10)


if __name__ == "__main__":
    main()
