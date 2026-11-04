"""Isolated kind proof: cluster snapshots, gateway decisions, bridge RBAC and Go verification."""

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from test_operator import CONTEXT, NS, action, kube, obj, policy, ready, wait

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8000/api/v1/ops/"
ACTOR = "system:serviceaccount:sentinel-lab:sentinel-operations-bridge"


def main() -> None:
    values = {k: v for k, v in dotenv_values(ROOT / ".env").items() if v is not None}
    env = {
        **values,
        **os.environ,
        "OPS_NAMESPACES": json.dumps([NS]),
        "OPS_APPROVAL_KEY_PATH": str(ROOT / ".cache/operator/approver.key"),
        "OPS_APPROVAL_KEY_ID": "local-operator",
    }
    directory = ROOT / ".cache/operations"
    directory.mkdir(parents=True, exist_ok=True)
    token = env["OPS_DEV_TOKEN"]

    def request(path: str, body: Any = None) -> Any:
        req = urllib.request.Request(
            BASE + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read())

    def collect() -> Any:
        subprocess.run(
            [
                sys.executable,
                "scripts/run_operations_bridge.py",
                "--context",
                CONTEXT,
                "--impersonate",
                ACTOR,
                "--once",
            ],
            cwd=ROOT,
            env=env,
            check=True,
            timeout=60,
        )
        return request("view")

    def decide(generation: int, value: str) -> dict[str, Any]:
        pending = wait(
            lambda: action(generation, "AwaitingApproval"), "native fault awaits gateway decision"
        )
        view = collect()
        row = next(
            r
            for r in view["resources"]
            if r["kind"] == "RemediationAction" and r["uid"] == pending["metadata"]["uid"]
        )
        result: dict[str, Any] = request(
            "actions/" + row["id"] + "/decision",
            {
                "decision": value,
                "expected_uid": row["uid"],
                "expected_version": row["resource_version"],
                "reason": "Isolated kind gateway acceptance test",
                "idempotency_key": "kind-gateway-" + row["uid"],
            },
        )
        assert result["state"] == "pending"
        collect()
        return result

    assert obj("deployment", "demo-recovery")["metadata"]["namespace"] == NS
    kube("apply", "-f", "infrastructure/kubernetes/operations/bridge-rbac.yaml")
    for verb, resource, namespace, expected in [
        ("patch", "deployments", NS, "no"),
        ("delete", "pods", NS, "no"),
        ("get", "secrets", NS, "no"),
        ("create", "remediationapprovals", NS, "yes"),
        ("list", "pods", "kube-system", "no"),
    ]:
        assert (
            kube(
                "auth",
                "can-i",
                verb,
                resource,
                "--as",
                ACTOR,
                "--namespace",
                namespace,
                check=False,
            )
            == expected
        )
    with (directory / "cluster-api.log").open("w") as output:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "kubesentinel_api.main:app",
                "--app-dir",
                "apps/api",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
                "--no-access-log",
            ],
            cwd=ROOT,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
        )
        try:

            def live() -> bool:
                try:
                    return bool(request("session")["subject"] == "local-admin")
                except OSError:
                    return False

            wait(live, "real API authenticated")
            initial = collect()
            assert initial["mode"] == "real" and initial["summary"]["nodes"] >= 1
            policy(
                dryRun=False,
                sustainSeconds=2,
                cooldownSeconds=0,
                maxActionsPerWindow=20,
                rollback={"enabled": False},
                verification={"timeoutSeconds": 90, "consecutiveSuccesses": 2},
            )
            kube("set", "env", "deployment/demo-recovery", "STARTUP_DELAY_SECONDS=25")
            ready()
            kube("scale", "deployment/demo-recovery", "--replicas=3")
            generation = int(obj("deployment", "demo-recovery")["metadata"]["generation"])
            rejection = decide(generation, "reject")
            rejected = wait(
                lambda: action(generation, "Rejected"), "gateway rejection prevents remediation"
            )
            assert obj("deployment", "demo-recovery")["spec"]["replicas"] == 3
            ready()
            kube("scale", "deployment/demo-recovery", "--replicas=2")
            ready()
            kube("scale", "deployment/demo-recovery", "--replicas=3")
            generation = int(obj("deployment", "demo-recovery")["metadata"]["generation"])
            approval = decide(generation, "approve")
            recovered = wait(
                lambda: action(generation, "Succeeded"),
                "Python-signed gateway approval verified by Go operator",
            )
            assert obj("deployment", "demo-recovery")["status"]["availableReplicas"] == 4
            view = collect()
            assert any(
                c["id"] == approval["id"] and c["state"] == "delivered" for c in view["commands"]
            )
            evidence = {
                "context": CONTEXT,
                "namespace": NS,
                "mode": "real",
                "resources": len(view["resources"]),
                "approval": approval,
                "rejection": rejection,
                "recovered_action": recovered,
                "rejected_action": rejected,
                "aws_resources": False,
            }
            (directory / "cluster-results.json").write_text(
                json.dumps(evidence, indent=2), encoding="utf-8"
            )
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    main()
