"""Real, destructive fault tests restricted to the dedicated disposable recovery kind cluster."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = "kind-kubesentinel-recovery"
NS = "sentinel-lab"
EVIDENCE = ROOT / ".cache/operator/evidence"


def kube(*args: str, data: dict[str, Any] | None = None, check: bool = True) -> str:
    result = subprocess.run(
        ["kubectl", "--context", CONTEXT, "-n", NS, *args],
        input=json.dumps(data) if data is not None else None,
        text=True,
        capture_output=True,
        check=False,
        timeout=150,
    )
    if check and result.returncode:
        raise RuntimeError(result.stderr[-4000:])
    return result.stdout.strip()


def obj(kind: str, name: str) -> dict[str, Any]:
    result: dict[str, Any] = json.loads(kube("get", kind, name, "-o", "json"))
    return result


def wait(check: Any, message: str, timeout: int = 180) -> Any:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = check()
        if result:
            print("PASS:", message, flush=True)
            return result
        time.sleep(2)
    raise AssertionError("Timed out: " + message)


def actions() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = json.loads(kube("get", "remediationactions", "-o", "json"))[
        "items"
    ]
    return result


def action(generation: int, phase: str) -> dict[str, Any] | None:
    return next(
        (
            row
            for row in actions()
            if row["spec"]["target"]["generation"] == generation
            and row.get("status", {}).get("phase") == phase
        ),
        None,
    )


def policy(**changes: Any) -> None:
    kube(
        "patch",
        "remediationpolicy",
        "lab-safe",
        "--type=merge",
        "-p",
        json.dumps({"spec": changes}),
    )


def mode(value: str) -> int:
    kube("set", "env", "deployment/demo-recovery", "MODE=" + value)
    return int(obj("deployment", "demo-recovery")["metadata"]["generation"])


def approve(row: dict[str, Any]) -> None:
    source = ROOT / ".cache/operator/action.json"
    source.write_text(json.dumps(row), encoding="utf-8")
    subprocess.run(
        ["go", "run", "./cmd/approval", "--action", str(source)],
        cwd=ROOT / "operator",
        check=True,
        timeout=120,
    )
    kube("apply", "-f", ".cache/operator/approval.json")


def ready() -> None:
    kube("rollout", "status", "deployment/demo-recovery", "--timeout=120s")


def main() -> None:
    os.environ.setdefault("GOTOOLCHAIN", "go1.26.8")
    os.environ.setdefault("GOCACHE", str(ROOT / ".cache/gobuild"))
    os.environ.setdefault("GOMODCACHE", str(ROOT / ".cache/gomod"))
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    assert (
        json.loads(kube("config", "view", "--minify", "-o", "json"))["contexts"][0]["name"]
        == CONTEXT
    )
    subject = "system:serviceaccount:sentinel-lab:sentinel-recovery"
    for verb, resource, namespace, expected in [
        ("delete", "pods", NS, "no"),
        ("get", "secrets", NS, "no"),
        ("patch", "deployments/arbitrary", NS, "no"),
        ("patch", "deployments/demo-recovery", "kube-system", "no"),
        ("create", "remediationapprovals", NS, "no"),
        ("update", "remediationactions", NS, "no"),
        ("patch", "deployments/demo-recovery", NS, "yes"),
    ]:
        result = kube(
            "auth",
            "can-i",
            verb,
            resource,
            "--as=" + subject,
            "--namespace=" + namespace,
            check=False,
        )
        assert result == expected, (verb, resource, namespace, result)
    print(
        "PASS: RBAC denies pod deletion, secrets, arbitrary/system workloads and self approval",
        flush=True,
    )
    # Create one already-unavailable pod in a surge rollout, preserving two healthy replicas.
    wait(
        lambda: any(
            row.get("status", {}).get("verifiedAt")
            for row in json.loads(kube("get", "verifiedrevisions", "-o", "json"))["items"]
        ),
        "healthy template independently certified before faults",
    )
    policy(
        sustainSeconds=2,
        cooldownSeconds=0,
        verification={"timeoutSeconds": 20, "consecutiveSuccesses": 2},
    )
    generation = mode("crash")
    dry = wait(lambda: action(generation, "DryRun"), "real crash produces dry-run decision")
    assert dry["status"].get("mutationCount", 0) == 0
    assert (
        obj("deployment", "demo-recovery")["spec"]["template"]["spec"]["containers"][0]["env"][0][
            "value"
        ]
        == "crash"
    )
    (EVIDENCE / "dry-run.json").write_text(json.dumps(dry, indent=2), encoding="utf-8")
    mode("healthy")
    ready()
    policy(dryRun=False, approvalRequired=True, rollback={"enabled": False})
    generation = mode("oom")
    pending = wait(
        lambda: action(generation, "AwaitingApproval"), "real OOM waits for signed approval"
    )
    assert pending["spec"]["kind"] == "Rollback"
    assert pending["status"].get("mutationCount", 0) == 0
    # Unsigned/fabricated approvals cannot authorize the exact same action.
    invalid = {
        "apiVersion": "recovery.kubesentinel.ai/v1alpha1",
        "kind": "RemediationApproval",
        "metadata": {"name": "invalid-signature", "namespace": NS},
        "spec": {
            "actionUID": pending["metadata"]["uid"],
            "actionDigest": "tampered",
            "expiresAt": pending["spec"]["expiresAt"],
            "keyID": "local-operator",
            "signature": "invalid",
        },
    }
    kube("apply", "-f", "-", data=invalid)
    time.sleep(7)
    assert action(generation, "AwaitingApproval")
    approve(pending)
    recovered = wait(
        lambda: action(generation, "Succeeded"),
        "approved verified-template rollback recovers OOM rollout",
    )
    assert recovered["status"]["approvalActor"] == "local-operator"
    assert recovered["status"]["successes"] >= 2
    assert recovered["status"]["before"]["requests"] >= 3
    assert recovered["status"]["after"]["errors"] == 0
    assert len(recovered["status"]["audit"]) >= 4
    (EVIDENCE / "approved-rollback.json").write_text(
        json.dumps(recovered, indent=2), encoding="utf-8"
    )
    ready()
    count = len(actions())
    time.sleep(12)
    assert len(actions()) == count, "same fault replay triggered duplicate action"
    print("PASS: duplicate reconciliation is idempotent", flush=True)
    # Signed Restart plus explicitly consented automatic rollback, bounded to two mutations.
    policy(maxActionsPerWindow=10, rollback={"enabled": True}, approvalRequired=True)
    generation = mode("not-ready")
    pending = wait(
        lambda: action(generation, "AwaitingApproval"),
        "readiness fault requires rollback-inclusive approval",
    )
    assert pending["spec"]["kind"] == "Restart" and pending["spec"]["budgetCost"] == 2
    approve(pending)
    undone = wait(
        lambda: action(generation, "RolledBack"),
        "failed restart verification triggers approved undo and re-verification",
    )
    assert undone["status"]["mutationCount"] == 2
    assert undone["status"]["phase"] != "Succeeded"
    (EVIDENCE / "failed-restart-undo.json").write_text(
        json.dumps(undone, indent=2), encoding="utf-8"
    )
    ready()
    # Cooldown refuses a new independent fault even when the policy allows execution.
    policy(cooldownSeconds=300, rollback={"enabled": False})
    generation = mode("crash")
    refused = wait(lambda: action(generation, "Rejected"), "cooldown rejects a new real fault")
    assert refused["status"]["reason"] == "CooldownActive"
    (EVIDENCE / "cooldown.json").write_text(json.dumps(refused, indent=2), encoding="utf-8")
    mode("healthy")
    ready()
    # Policy maintenance and global installation fences reject stale/unsafe plans.
    policy(cooldownSeconds=0, maintenanceWindows=[])
    generation = mode("crash")
    refused = wait(
        lambda: action(generation, "Rejected"),
        "maintenance default-deny rejects fault outside authorized window",
    )
    assert refused["status"]["reason"] == "OutsideMaintenanceWindow"
    mode("healthy")
    ready()
    # All safety-relevant specs are immutable in the real API server.
    row = actions()[0]
    patch_result = subprocess.run(
        [
            "kubectl",
            "--context",
            CONTEXT,
            "-n",
            NS,
            "patch",
            "remediationaction",
            row["metadata"]["name"],
            "--type=merge",
            "-p",
            '{"spec":{"scaleTo":99}}',
        ],
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert patch_result.returncode != 0 and "immutable" in patch_result.stderr
    print("PASS: CRD admission enforces immutable action plans", flush=True)
    # A controlled slow-start replica shortage exercises the real bounded scale patch.
    policy(
        maintenanceWindows=[{"weekdays": list(range(7)), "startHour": 0, "endHour": 24}],
        cooldownSeconds=0,
        maxActionsPerWindow=20,
        rollback={"enabled": False},
        verification={"timeoutSeconds": 90, "consecutiveSuccesses": 2},
    )
    kube("set", "env", "deployment/demo-recovery", "STARTUP_DELAY_SECONDS=25")
    ready()
    kube("scale", "deployment/demo-recovery", "--replicas=3")
    generation = int(obj("deployment", "demo-recovery")["metadata"]["generation"])
    pending = wait(
        lambda: action(generation, "AwaitingApproval"),
        "real replica shortage requires scale approval",
    )
    assert pending["spec"]["kind"] == "Scale" and pending["spec"]["scaleTo"] == 4
    approve(pending)
    scaled = wait(
        lambda: action(generation, "Succeeded"),
        "approved scale respects bounds and verifies four available replicas",
    )
    assert obj("deployment", "demo-recovery")["status"]["availableReplicas"] == 4
    (EVIDENCE / "approved-scale.json").write_text(json.dumps(scaled, indent=2), encoding="utf-8")
    (EVIDENCE / "all-actions.json").write_text(json.dumps(actions(), indent=2), encoding="utf-8")
    (EVIDENCE / "summary.json").write_text(
        json.dumps(
            {
                "context": CONTEXT,
                "namespace": NS,
                "result": "passed",
                "action_records": len(actions()),
                "aws_resources": False,
                "scope": "native faults, signed approvals, verification, undo, RBAC and rejection",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("PASS: real isolated recovery acceptance", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(
            kube("get", "pods,remediationactions,events", "-o", "wide", check=False),
            file=sys.stderr,
        )
        raise
