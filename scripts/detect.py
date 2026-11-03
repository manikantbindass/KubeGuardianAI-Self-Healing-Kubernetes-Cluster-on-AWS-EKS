"""Poll real telemetry, retaining history for lag features; publish only by explicit opt-in."""

import argparse
import json
import os
import sys
import time
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))

from kubesentinel_ml.collection import collect  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prometheus", default="http://127.0.0.1:9090")
    parser.add_argument("--loki", default="http://127.0.0.1:3100")
    parser.add_argument("--detector", default="http://127.0.0.1:8010")
    parser.add_argument("--kube-context")
    parser.add_argument("--polls", type=int, default=1, help="0 runs until interrupted")
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    if args.polls < 0:
        parser.error("--polls must be nonnegative")
    index = 0
    while args.polls == 0 or index < args.polls:
        end = datetime.now(UTC).replace(second=0, microsecond=0)
        try:
            rows, collection = collect(
                args.prometheus,
                args.loki,
                end - timedelta(minutes=5),
                end - timedelta(microseconds=1),
                "live-export",
                args.kube_context,
            )
            request = urllib.request.Request(
                args.detector.rstrip("/") + "/api/v1/score",
                data=json.dumps(
                    {
                        "observations": [r.model_dump(mode="json") for r in rows],
                        "score_from": (end - timedelta(minutes=1)).isoformat(),
                        "publish": args.publish,
                    }
                ).encode(),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + os.environ.get("DETECTOR_API_TOKEN", ""),
                },
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=15) as response:
                print(json.dumps({"collection": collection, "result": json.load(response)}))
        except (OSError, ValueError) as error:
            print(
                json.dumps({"status": "telemetry_unavailable", "error_type": type(error).__name__}),
                file=sys.stderr,
            )
            if args.polls == 1:
                raise SystemExit(1) from None
        index += 1
        if args.polls == 0 or index < args.polls:
            time.sleep(60)


if __name__ == "__main__":
    main()
