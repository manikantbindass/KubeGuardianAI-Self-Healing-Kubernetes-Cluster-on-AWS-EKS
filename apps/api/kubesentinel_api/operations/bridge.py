"""Scoped Kubernetes mirror and decision delivery; no Deployment or pod mutation client."""

import argparse
import hashlib
import importlib
import json
import time
import urllib.request
from datetime import UTC, datetime
from typing import Any

from kubesentinel_api.config import get_settings

GROUP = "recovery.kubesentinel.ai"
VERSION = "v1alpha1"
REJECT = "recovery.kubesentinel.ai/rejected-by"


def plan_digest(spec: dict[str, Any]) -> str:
    """Match Go ActionSpec struct order/omitempty, not arbitrary Kubernetes JSON key order."""
    ordered: dict[str, Any] = {
        "incident": {
            k: spec["incident"][k] for k in ("id", "type", "source", "severity", "observedAt")
        },
        "policyName": spec["policyName"],
        "policyUID": spec["policyUID"],
        "policyVersion": spec["policyVersion"],
        "target": {
            k: spec["target"][k]
            for k in ("name", "uid", "generation", "templateDigest", "replicas")
        },
        "kind": spec["kind"],
    }
    for key in ("scaleTo", "revisionName", "beforeRevision"):
        if spec.get(key):
            ordered[key] = spec[key]
    for key in ("rollbackEnabled", "budgetCost", "expiresAt"):
        ordered[key] = spec[key]
    raw = json.dumps(ordered, ensure_ascii=False, separators=(",", ":"))
    # encoding/json's HTML-safe representation is part of the signed-plan wire contract.
    for character, escaped in (
        ("&", "\\u0026"),
        ("<", "\\u003c"),
        (">", "\\u003e"),
        ("\u2028", "\\u2028"),
        ("\u2029", "\\u2029"),
    ):
        raw = raw.replace(character, escaped)
    return hashlib.sha256(raw.encode()).hexdigest()


def api_call(base: str, token: str, path: str, payload: object | None = None) -> Any:
    req = urllib.request.Request(
        base.rstrip("/") + "/api/v1/ops/" + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError("Operations response exceeds limit")
    return json.loads(raw)


def metadata_row(kind: str, metadata: Any, namespace: str, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": kind,
        "namespace": namespace,
        "name": metadata.name,
        "uid": metadata.uid,
        "resource_version": metadata.resource_version,
        "collected_at": datetime.now(UTC).isoformat(),
        "data": data,
    }


class Bridge:
    def __init__(self, core: Any, apps: Any, custom: Any, namespaces: list[str]) -> None:
        self.core, self.apps, self.custom, self.namespaces = core, apps, custom, namespaces

    def batches(self) -> list[dict[str, Any]]:
        from kubernetes.client.exceptions import ApiException

        output = []
        nodes = self.core.list_node(limit=100, _request_timeout=5)
        rows = []
        for node in nodes.items:
            conditions = [
                {"type": c.type, "status": c.status, "reason": c.reason}
                for c in node.status.conditions or []
            ]
            capacity = node.status.allocatable or {}
            rows.append(
                metadata_row(
                    "Node",
                    node.metadata,
                    "",
                    {
                        "healthy": any(
                            c["type"] == "Ready" and c["status"] == "True" for c in conditions
                        ),
                        "conditions": conditions,
                        "cpu_capacity": capacity.get("cpu"),
                        "memory_capacity": capacity.get("memory"),
                        "labels": {
                            k: v
                            for k, v in (node.metadata.labels or {}).items()
                            if k in {"kubernetes.io/hostname", "node.kubernetes.io/instance-type"}
                        },
                        "collection_truncated": bool(nodes.metadata._continue),
                    },
                )
            )
        output.append(
            {
                "mode": "real",
                "rows": rows,
                "replace_scopes": [] if nodes.metadata._continue else ["Node:"],
            }
        )
        for namespace in self.namespaces:
            for kind, fetch in (
                ("Deployment", self.apps.list_namespaced_deployment),
                ("Pod", self.core.list_namespaced_pod),
                ("Event", self.core.list_namespaced_event),
            ):
                result = fetch(namespace, limit=100, _request_timeout=5)
                rows = []
                for item in result.items:
                    if kind == "Deployment":
                        spec, status = item.spec, item.status
                        desired = spec.replicas or 0
                        containers = spec.template.spec.containers
                        data = {
                            "desired": desired,
                            "ready": status.available_replicas or 0,
                            "healthy": desired > 0
                            and status.available_replicas == desired
                            and status.updated_replicas == desired
                            and (status.observed_generation or 0) >= item.metadata.generation,
                            "labels": item.metadata.labels or {},
                            "images": [c.image for c in containers],
                            "conditions": [
                                {"type": c.type, "status": c.status, "reason": c.reason}
                                for c in status.conditions or []
                            ],
                        }
                    elif kind == "Pod":
                        statuses = item.status.container_statuses or []
                        containers = item.spec.containers
                        data = {
                            "phase": item.status.phase,
                            "ready": sum(bool(s.ready) for s in statuses),
                            "desired": len(containers),
                            "restarts": sum(s.restart_count or 0 for s in statuses),
                            "node": item.spec.node_name,
                            "owner": next(
                                (
                                    o.name
                                    for o in item.metadata.owner_references or []
                                    if o.controller
                                ),
                                "",
                            ),
                            "containers": [c.name for c in containers],
                            "images": [c.image for c in containers],
                            "conditions": [
                                {"type": c.type, "status": c.status, "reason": c.reason}
                                for c in item.status.conditions or []
                            ],
                        }
                    else:
                        containers = []
                        timestamp = (
                            item.last_timestamp
                            or item.event_time
                            or item.metadata.creation_timestamp
                        )
                        data = {
                            "type": item.type,
                            "reason": item.reason,
                            "message": (item.message or "")[:512],
                            "owner": item.involved_object.name,
                            "timestamp": timestamp.isoformat() if timestamp else None,
                        }
                    if containers:
                        # Configuration only; no environment values, secret refs or volumes.
                        requests = [
                            (c.resources.requests or {}) if c.resources else {} for c in containers
                        ]
                        data["cpu_request"] = (
                            " + ".join(str(v["cpu"]) for v in requests if "cpu" in v) or None
                        )
                        data["memory_request"] = (
                            " + ".join(str(v["memory"]) for v in requests if "memory" in v) or None
                        )
                    data["collection_truncated"] = bool(result.metadata._continue)
                    rows.append(metadata_row(kind, item.metadata, namespace, data))
                output.append(
                    {
                        "mode": "real",
                        "rows": rows,
                        "replace_scopes": []
                        if result.metadata._continue
                        else [f"{kind}:{namespace}"],
                    }
                )
            for kind, plural in (
                ("RemediationAction", "remediationactions"),
                ("RemediationPolicy", "remediationpolicies"),
            ):
                try:
                    result = self.custom.list_namespaced_custom_object(
                        GROUP, VERSION, namespace, plural, limit=100, _request_timeout=5
                    )
                except ApiException as error:
                    if error.status != 404:
                        raise
                    continue
                rows = []
                for item in result["items"]:
                    meta = item["metadata"]
                    data = {
                        "spec": item["spec"],
                        "status": item.get("status", {}),
                        "collection_truncated": bool(result.get("metadata", {}).get("continue")),
                    }
                    if kind == "RemediationAction":
                        data["planDigest"] = plan_digest(item["spec"])
                    rows.append(
                        {
                            "kind": kind,
                            "namespace": namespace,
                            "name": meta["name"],
                            "uid": meta["uid"],
                            "resource_version": meta["resourceVersion"],
                            "collected_at": datetime.now(UTC).isoformat(),
                            "data": data,
                        }
                    )
                # Preserve action history in PostgreSQL when a cluster resource later disappears.
                output.append(
                    {
                        "mode": "real",
                        "rows": rows,
                        "replace_scopes": [f"{kind}:{namespace}"]
                        if kind == "RemediationPolicy"
                        and not result.get("metadata", {}).get("continue")
                        else [],
                    }
                )
        return output

    def deliver(self, command: dict[str, Any]) -> str:
        from kubernetes.client.exceptions import ApiException

        kind, namespace, name = command["kind"], command["namespace"], command["target"]
        if namespace not in self.namespaces or namespace.startswith("kube-"):
            raise ValueError("Command namespace is outside bridge scope")
        payload = command["payload"]
        plural = "remediationpolicies" if kind == "policy" else "remediationactions"
        live = self.custom.get_namespaced_custom_object(
            GROUP, VERSION, namespace, plural, name, _request_timeout=5
        )
        if live["metadata"]["uid"] != payload["uid"]:
            raise ValueError("Target UID changed")
        if (
            kind == "reject"
            and live["metadata"].get("annotations", {}).get(REJECT) == payload["actor"]
        ):
            return "Rejection annotation already persisted; inspect operator result"
        if kind == "policy" and all(live["spec"].get(k) == v for k, v in payload["spec"].items()):
            return "Requested policy values are already present"
        if kind == "approve":
            approval = payload["approval"]
            if (
                approval["metadata"]["namespace"] != namespace
                or approval["spec"]["actionUID"] != payload["uid"]
            ):
                raise ValueError("Approval binding mismatch")
            try:
                existing = self.custom.get_namespaced_custom_object(
                    GROUP,
                    VERSION,
                    namespace,
                    "remediationapprovals",
                    approval["metadata"]["name"],
                    _request_timeout=5,
                )
                if existing["spec"] != approval["spec"]:
                    raise ValueError("Conflicting existing approval")
                return "Exact signed approval was already persisted"
            except ApiException as error:
                if error.status != 404:
                    raise
        if live["metadata"]["resourceVersion"] != payload["resourceVersion"]:
            raise ValueError("Resource version changed before command delivery")
        if kind != "policy" and live.get("status", {}).get("phase") != "AwaitingApproval":
            raise ValueError("Action no longer awaits approval")
        if kind == "approve":
            if plan_digest(live["spec"]) != payload["approval"]["spec"]["actionDigest"]:
                raise ValueError("Plan digest changed")
            self.custom.create_namespaced_custom_object(
                GROUP,
                VERSION,
                namespace,
                "remediationapprovals",
                payload["approval"],
                _request_timeout=5,
            )
            return "Signed approval persisted; operator independently decides execution"
        patch = [
            {"op": "test", "path": "/metadata/uid", "value": payload["uid"]},
            {
                "op": "test",
                "path": "/metadata/resourceVersion",
                "value": payload["resourceVersion"],
            },
        ]
        if kind == "reject":
            annotations = live["metadata"].get("annotations", {})
            annotations[REJECT] = payload["actor"]
            patch.append({"op": "add", "path": "/metadata/annotations", "value": annotations})
        elif kind == "policy":
            patch.extend(
                {"op": "replace", "path": "/spec/" + key, "value": value}
                for key, value in payload["spec"].items()
            )
        else:
            raise ValueError("Unsupported bridge command")
        self.custom.api_client.call_api(
            "/apis/{group}/{version}/namespaces/{namespace}/{plural}/{name}",
            "PATCH",
            path_params={
                "group": GROUP,
                "version": VERSION,
                "namespace": namespace,
                "plural": plural,
                "name": name,
            },
            query_params=[],
            header_params={
                "Content-Type": "application/json-patch+json",
                "Accept": "application/json",
            },
            body=patch,
            response_type="object",
            auth_settings=["BearerToken"],
            _return_http_data_only=True,
            _request_timeout=5,
        )
        return "Version-fenced request persisted; inspect resulting resource state"


def main() -> None:
    client = importlib.import_module("kubernetes.client")
    config = importlib.import_module("kubernetes.config")

    parser = argparse.ArgumentParser(description=__doc__)
    location = parser.add_mutually_exclusive_group(required=True)
    location.add_argument("--context")
    location.add_argument("--in-cluster", action="store_true")
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--impersonate", help="CI/local admin launcher only; restrict reads/writes to this SA"
    )
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=int, default=10)
    args = parser.parse_args()
    if not 5 <= args.interval <= 60:
        parser.error("interval must be 5..60 seconds")
    if args.in_cluster:
        config.load_incluster_config()
    else:
        config.load_kube_config(context=args.context)
    api_client = client.ApiClient()
    if args.impersonate:
        api_client.default_headers["Impersonate-User"] = args.impersonate
    settings = get_settings()
    token = settings.ops_bridge_token.get_secret_value()
    if not token:
        raise SystemExit("OPS_BRIDGE_TOKEN is required")
    connector = Bridge(
        client.CoreV1Api(api_client),
        client.AppsV1Api(api_client),
        client.CustomObjectsApi(api_client),
        settings.ops_namespaces,
    )
    while True:
        try:
            batches = connector.batches()
            for batch in batches:
                api_call(args.api, token, "internal/snapshots", batch)
            commands = api_call(args.api, token, "internal/commands")
            for command in commands:
                try:
                    result = connector.deliver(command)
                    state = "delivered"
                except Exception as error:
                    result, state = (
                        f"Delivery refused/unavailable ({type(error).__name__}); inspect resource",
                        "failed",
                    )
                api_call(
                    args.api,
                    token,
                    "internal/commands/" + command["id"],
                    {"state": state, "result": result},
                )
            print(
                json.dumps(
                    {
                        "event": "bridge_cycle",
                        "records": sum(len(b["rows"]) for b in batches),
                        "commands": len(commands),
                    }
                ),
                flush=True,
            )
        except Exception as error:
            print(
                json.dumps({"event": "bridge_unavailable", "error_type": type(error).__name__}),
                flush=True,
            )
            if args.once:
                raise SystemExit(1) from None
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
