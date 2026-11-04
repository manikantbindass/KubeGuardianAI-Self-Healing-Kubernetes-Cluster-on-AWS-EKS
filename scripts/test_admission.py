"""Exercise native digest admission in the disposable local kind CI cluster only."""

from __future__ import annotations

import copy
import json
import subprocess
from typing import Any

CONTEXT = "kind-kubesentinel"
NAMESPACE = "sentinel-admission-test"
PREFIX = "123456789012.dkr.ecr.ap-south-1.amazonaws.com/sentinel"


def kubectl(*args: str, value: Any = None, success: bool = True) -> None:
    result = subprocess.run(
        ["kubectl", "--context", CONTEXT, *args],
        input=json.dumps(value) if value else None,
        text=True,
        capture_output=True,
        check=False,
    )
    if (result.returncode == 0) != success:
        raise RuntimeError(result.stdout + result.stderr)
    if not success and "sentinel-immutable-images" not in result.stderr:
        raise RuntimeError("Request failed for a reason other than expected admission denial")


def main() -> None:
    namespace = {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {
            "name": NAMESPACE,
            "labels": {"delivery.kubesentinel.ai/enforce": "true"},
            "annotations": {"delivery.kubesentinel.ai/registry-prefix": PREFIX},
        },
    }
    policy = "infrastructure/kubernetes/security/digest-admission.yaml"
    try:
        kubectl("apply", "-f", policy)
        kubectl("apply", "-f", "-", value=namespace)
        # Force a resource-version observation before checking propagation.
        import time

        time.sleep(3)
        pod: dict[str, Any] = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": "digest-contract",
                "namespace": NAMESPACE,
            },
            "spec": {"containers": [{"name": "api", "image": PREFIX + "/api@sha256:" + "a" * 64}]},
        }
        kubectl("create", "--dry-run=server", "-f", "-", value=pod)
        for image in (
            PREFIX + "/api:latest",
            PREFIX.replace("123456789012", "999999999999") + "/api@sha256:" + "a" * 64,
        ):
            invalid = copy.deepcopy(pod)
            invalid["spec"]["containers"][0]["image"] = image
            kubectl("create", "--dry-run=server", "-f", "-", value=invalid, success=False)
        invalid = copy.deepcopy(pod)
        invalid["spec"]["initContainers"] = [{"name": "init", "image": PREFIX + "/api:latest"}]
        kubectl("create", "--dry-run=server", "-f", "-", value=invalid, success=False)
        print("PASS: approved digest accepted; tags, foreign registry and mutable init denied")
    finally:
        kubectl("delete", "namespace", NAMESPACE, "--ignore-not-found")
        kubectl("delete", "-f", policy, "--ignore-not-found")


if __name__ == "__main__":
    main()
