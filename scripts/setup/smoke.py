"""HTTP smoke for native or Compose: health/readiness, dashboard proxy, durable worker."""

import argparse
import json
import time
import urllib.error
import urllib.request
from typing import Any


def request(url: str, payload: dict[str, str] | None = None) -> tuple[int, Any]:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            body = response.read().decode()
            return response.status, json.loads(body) if "json" in response.headers.get(
                "Content-Type", ""
            ) else body
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--dashboard", default="http://127.0.0.1:3000")
    parser.add_argument("--expect-unavailable", action="store_true")
    args = parser.parse_args()
    status, page = request(args.dashboard.rstrip("/") + "/status")
    assert status == 200 and "System status" in page, "Dashboard did not render"
    status, proxied = request(f"{args.dashboard}/api/backend/health")
    if args.expect_unavailable:
        assert status == 503, (status, proxied)
        print("PASS: dashboard remains available and proxy reports backend unavailable")
        return
    assert status == 200 and proxied["status"] == "ok", (status, proxied)
    status, health = request(f"{args.api}/api/v1/health")
    assert status == 200 and health == proxied
    status, ready = request(f"{args.api}/api/v1/ready")
    assert status == 200 and ready["status"] == "ready", ready
    status, job = request(f"{args.dashboard}/api/backend/jobs", {"name": "Smoke test"})
    assert status == 202 and job["status"] == "queued", job
    for _ in range(30):
        status, result = request(f"{args.api}/api/v1/jobs/{job['id']}")
        if status == 200 and result["status"] == "completed":
            assert "Smoke test" in result["message"]
            print("PASS: health/readiness, dashboard proxy, durable job, worker and cache path")
            return
        time.sleep(1)
    raise AssertionError("Worker did not complete the greeting within 30 seconds")


if __name__ == "__main__":
    main()
