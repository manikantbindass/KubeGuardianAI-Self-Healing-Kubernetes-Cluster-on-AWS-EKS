"""Explicit small synthetic operations fixture; never imported into real mode."""

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any


def fixture() -> dict[str, Any]:
    now = datetime.now(UTC)
    rows = []

    def add(kind: str, name: str, data: dict[str, Any], namespace: str = "sentinel-lab") -> None:
        rows.append(
            {
                "kind": kind,
                "namespace": namespace,
                "name": name,
                "uid": "synthetic-" + hashlib.sha256(f"{kind}:{name}".encode()).hexdigest()[:24],
                "resource_version": "1",
                "collected_at": now.isoformat(),
                "data": data,
            }
        )

    for index in range(3):
        add(
            "Node",
            f"demo-node-{index + 1}",
            {
                "healthy": True,
                "cpu_capacity": "4",
                "memory_capacity": "8Gi",
                "conditions": [{"type": "Ready", "status": "True"}],
            },
            "",
        )
    names = [
        "checkout-api",
        "payment-service",
        "inventory-worker",
        "frontend",
        "notification-service",
        "catalog-api",
    ]
    for index, name in enumerate(names):
        healthy = index not in (0, 1)
        add(
            "Deployment",
            name,
            {
                "healthy": healthy,
                "ready": 3 if healthy else 2,
                "desired": 3,
                "cpu_request": "300m",
                "memory_request": "256Mi",
                "images": [f"synthetic/{name}:fixture"],
                "conditions": [{"type": "Available", "status": "True" if healthy else "False"}],
            },
        )
        for pod in range(3):
            add(
                "Pod",
                f"{name}-demo-{pod}",
                {
                    "phase": "Running" if healthy or pod else "CrashLoopBackOff",
                    "ready": 1 if healthy or pod else 0,
                    "desired": 1,
                    "restarts": 0 if healthy else 4 + pod,
                    "node": f"demo-node-{pod + 1}",
                    "cpu_request": "100m",
                    "memory_request": "128Mi",
                    "owner": name,
                    "containers": [name],
                    "images": [f"synthetic/{name}:fixture"],
                    "logs": [
                        f"{now.isoformat()} INFO synthetic workload fixture; not production logs"
                    ],
                },
            )
    reasons = [
        ("OOMKilled", "critical", "checkout-api"),
        ("LatencyDegradation", "warning", "payment-service"),
        ("ReplicaShortage", "warning", "inventory-worker"),
        ("ReadinessProbeFailure", "warning", "checkout-api"),
    ]
    for index, (reason, severity, resource) in enumerate(reasons):
        at = (now - timedelta(minutes=3 + index * 7)).isoformat()
        incident = {
            "id": f"synthetic-incident-{index}",
            "source": "synthetic-fixture",
            "namespace": "sentinel-lab",
            "resource": resource,
            "reason": reason,
            "summary": f"Explicit synthetic demonstration of {reason} affecting {resource}.",
            "severity": severity,
            "status": "open",
            "first_seen": at,
            "last_seen": at,
            "occurrences": index + 1,
            "confidence": None,
            "confidence_label": "Uncalibrated synthetic score",
            "review": None,
        }
        add(
            "Event",
            f"synthetic-event-{index}",
            {
                "type": "Warning",
                "reason": reason,
                "message": incident["summary"],
                "owner": resource,
                "timestamp": at,
                "demoIncident": incident,
                "demoAnomaly": {
                    "incident_id": incident["id"],
                    "at": at,
                    "resource": resource,
                    "detector": "robust_statistics",
                    "model_version": "synthetic-fixture-v1",
                    "score": 4.5 + index * 1.3,
                    "threshold": 4,
                    "provenance": "synthetic",
                    "score_kind": "uncalibrated_anomaly_score",
                    "explanations": [
                        {
                            "feature": "memory_ratio",
                            "value": 0.98,
                            "reference": 0.45,
                            "detail": "Synthetic robust deviation; not causal attribution",
                        },
                        {
                            "feature": "restart_frequency",
                            "value": 6,
                            "reference": 0,
                            "detail": "Synthetic fixture, explicit demonstration only",
                        },
                        {
                            "feature": "latency_p95_ms",
                            "value": 650,
                            "reference": 100,
                            "detail": "Synthetic deviation from fixture baseline",
                        },
                    ],
                },
            },
        )
    policy = {
        "namespaceAllowlist": ["sentinel-lab"],
        "workloadSelector": {"matchLabels": {"app": "checkout-api"}},
        "incidentTypes": [
            "OOMKilled",
            "CrashLoopBackOff",
            "ReadinessProbeFailure",
            "ReplicaShortage",
        ],
        "allowedActions": ["Restart", "Scale", "Rollback", "Escalate"],
        "dryRun": True,
        "minimumSeverity": "warning",
        "approvalRequired": True,
        "cooldownSeconds": 300,
        "maxActionsPerWindow": 2,
        "actionWindowSeconds": 3600,
        "minimumHealthyReplicas": 1,
        "minimumReplicas": 1,
        "maximumReplicas": 4,
        "scaleStep": 1,
        "maintenanceWindows": [{"weekdays": list(range(7)), "startHour": 0, "endHour": 24}],
        "escalationDestination": "synthetic-platform-team",
        "maxIncidentAgeSeconds": 300,
        "sustainSeconds": 60,
        "verification": {
            "servicePort": 8080,
            "path": "/health",
            "timeoutSeconds": 120,
            "consecutiveSuccesses": 3,
            "samples": 5,
            "maxErrorBasisPoints": 100,
            "maxP95Milliseconds": 500,
            "maxLatencyPercent": 150,
        },
        "rollback": {"enabled": False, "maxRevisionAgeSeconds": 3600},
    }
    add("RemediationPolicy", "workload-safe-recovery", {"spec": policy})
    for index, phase in enumerate(("AwaitingApproval", "Succeeded", "DryRun", "RolledBack")):
        at = (now - timedelta(minutes=5 + index * 12)).isoformat()
        add(
            "RemediationAction",
            f"synthetic-recovery-{index + 1}",
            {
                "spec": {
                    "incident": {
                        "id": f"synthetic-incident-{index}",
                        "type": reasons[index][0],
                        "source": "kubernetes",
                        "severity": reasons[index][1],
                        "observedAt": at,
                    },
                    "policyName": "workload-safe-recovery",
                    "policyUID": "synthetic-policy",
                    "policyVersion": "1",
                    "target": {
                        "name": reasons[index][2],
                        "uid": "synthetic-workload",
                        "generation": 3,
                        "templateDigest": "0" * 64,
                        "replicas": 3,
                    },
                    "kind": "Rollback" if index == 0 else "Restart",
                    "rollbackEnabled": index == 3,
                    "budgetCost": 2 if index == 3 else 1,
                    "expiresAt": (now + timedelta(minutes=4)).isoformat().replace("+00:00", "Z"),
                },
                "planDigest": "0" * 64,
                "status": {
                    "phase": phase,
                    "reason": "Synthetic demonstration record; no cluster action occurred",
                    "mutationCount": 0 if index in (0, 2) else 2 if index == 3 else 1,
                    "approvalActor": "synthetic-approver" if index in (1, 3) else None,
                    "successes": 3 if index in (1, 3) else 0,
                    "before": {"errors": 1, "requests": 5, "p95Milliseconds": 650},
                    "after": {"errors": 0, "requests": 5, "p95Milliseconds": 23}
                    if index in (1, 3)
                    else None,
                    "audit": [
                        {
                            "at": at,
                            "actor": "synthetic-operator",
                            "state": "Observing",
                            "reason": "Explicit synthetic fixture",
                        },
                        {
                            "at": at,
                            "actor": "synthetic-operator",
                            "state": phase,
                            "reason": "No actual execution",
                        },
                    ],
                },
            },
        )
    return {
        "mode": "demo",
        "rows": rows,
        "replace_scopes": [
            f"{kind}:{namespace}"
            for kind, namespace in sorted({(r["kind"], r["namespace"]) for r in rows})
        ],
    }
