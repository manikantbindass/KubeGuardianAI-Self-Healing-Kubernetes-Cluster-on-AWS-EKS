"""Explicitly authorized faults in a dedicated disposable kind cluster only."""

from __future__ import annotations

import argparse
import json
import subprocess
from urllib.parse import urlparse

CONTEXT = "kind-kubesentinel-resilience"
NAMESPACE = "sentinel-chaos"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=["terminate-pod", "rollout-failure", "node-drain"])
    parser.add_argument("--authorize-destructive", action="store_true")
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    if not args.authorize_destructive:
        raise SystemExit("Explicit destructive lab authorization is required")
    prefix = ["kubectl", "--context", CONTEXT]
    clusters = subprocess.check_output(["kind", "get", "clusters"], text=True).splitlines()
    if "kubesentinel-resilience" not in clusters:
        raise SystemExit("Dedicated disposable kind cluster does not exist")
    config = json.loads(
        subprocess.check_output([*prefix, "config", "view", "--minify", "-o", "json"], text=True)
    )
    server = config["clusters"][0]["cluster"]["server"]
    if urlparse(server).hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("Cluster API endpoint must be loopback")
    namespace = json.loads(
        subprocess.check_output([*prefix, "get", "namespace", NAMESPACE, "-o", "json"], text=True)
    )
    if namespace["metadata"].get("labels", {}).get("sentinel.ai/disposable") != "true":
        raise SystemExit("Disposable namespace marker is required")
    if args.scenario == "node-drain":
        if not args.target.startswith("kubesentinel-resilience-worker"):
            raise SystemExit("Only dedicated kind workers can be drained")
        command = [*prefix, "drain", args.target, "--ignore-daemonsets", "--timeout=60s"]
    else:
        kind = "pod" if args.scenario == "terminate-pod" else "deployment"
        item = json.loads(
            subprocess.check_output(
                [*prefix, "-n", NAMESPACE, "get", kind, args.target, "-o", "json"], text=True
            )
        )
        if item["metadata"].get("labels", {}).get("sentinel.ai/fault-target") != "true":
            raise SystemExit("Target must explicitly opt in to fault injection")
        if args.scenario == "terminate-pod":
            command = [*prefix, "-n", NAMESPACE, "delete", "pod", args.target, "--wait=false"]
        else:
            command = [
                *prefix,
                "-n",
                NAMESPACE,
                "set",
                "image",
                "deployment/" + args.target,
                "demo=invalid.example.invalid/fault:deliberate",
            ]
    subprocess.run(command, check=True)
    print("Fault injected; collect evidence and restore using the resilience runbook")


if __name__ == "__main__":
    main()
