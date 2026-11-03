"""Validate release evidence and prepare reviewed GitOps changes; never sync a cluster."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = {"api", "dashboard", "operator", "detector", "demo-workload"}
REPO = "manikantbindass/KubeSentinel-AI"
REQUIRED_CHECKS = {
    "portfolio",
    "api (ubuntu-latest)",
    "api (windows-latest)",
    "dashboard",
    "migrations",
    "containers",
    "kind",
    "telemetry",
    "browser",
    "cluster",
    "isolated-recovery",
    "go-checks (ubuntu-latest)",
    "go-checks (windows-latest)",
    "reproducibility (ubuntu-latest)",
    "reproducibility (windows-latest)",
    "detector-container",
    "validate",
    "security-static",
    "resilience",
    *(f"image-security ({name})" for name in COMPONENTS),
}


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def validate_release(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "version",
        "source_commit",
        "run_id",
        "repository",
        "images",
    }:
        raise ValueError("Release fields must be exact")
    if value["schema_version"] != 1 or value["repository"] != REPO:
        raise ValueError("Untrusted release repository/schema")
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+(?:-rc\.[0-9]+)?", value["version"]):
        raise ValueError("Version must be vMAJOR.MINOR.PATCH or -rc.N")
    if not re.fullmatch(r"[a-f0-9]{40}", value["source_commit"]):
        raise ValueError("Source must be an immutable commit")
    if not re.fullmatch(r"[1-9][0-9]{0,19}", str(value["run_id"])):
        raise ValueError("Invalid release run ID")
    if set(value["images"]) != COMPONENTS:
        raise ValueError("Missing or unexpected release components")
    registries = set()
    for name, image in value["images"].items():
        if not isinstance(image, str) or not re.fullmatch(
            r"[0-9]{12}\.dkr\.ecr\.[a-z]{2}-[a-z]+-[0-9]\.amazonaws\.com/"
            r"[a-z][a-z0-9-]{2,35}/" + re.escape(name) + r"@sha256:[a-f0-9]{64}",
            image,
        ):
            raise ValueError(f"Invalid immutable ECR image: {name}")
        registries.add(image.split("/")[0])
    if len(registries) != 1:
        raise ValueError("Release spans multiple accounts/regions")
    return value


def validate_receipt(receipt: Any, release: Any, now: datetime | None = None) -> None:
    if receipt.get("release_sha256") != digest(release):
        raise ValueError("Staging verification does not match this exact release")
    if receipt.get("namespace") != "sentinel-staging" or receipt.get("status") != "verified":
        raise ValueError("Missing successful staging verification")
    timestamp = datetime.fromisoformat(receipt["observed_at"])
    current = now or datetime.now(UTC)
    if timestamp.tzinfo is None or not timedelta(0) <= current - timestamp <= timedelta(hours=24):
        raise ValueError("Staging verification is stale or from the future")
    if set(receipt.get("deployments", {})) != {"api", "dashboard", "worker"}:
        raise ValueError("Incomplete staging deployment evidence")
    for name, item in receipt["deployments"].items():
        expected = release["images"]["api" if name == "worker" else name]
        if item.get("image") != expected or item.get("ready", 0) < 2:
            raise ValueError("Staging images/readiness do not match")


def promote(release: Any, environment: str, root: Path = ROOT) -> list[Path]:
    release = validate_release(release)
    if environment not in {"staging", "production"}:
        raise ValueError("Unsupported deployment environment")
    environments = root / "infrastructure/argocd/environments"
    if environment == "production":
        if read(environments / "staging/release.json") != release:
            raise ValueError("Production must promote exactly the staged release")
        validate_receipt(read(environments / "staging/verification.json"), release)
    target = environments / environment
    app = read(target / "application.json")
    if app["spec"]["destination"]["namespace"] != "sentinel-" + environment:
        raise ValueError("Application destination mismatch")
    app["spec"]["sources"][0]["targetRevision"] = release["source_commit"]
    app["metadata"]["annotations"]["delivery.kubesentinel.ai/state"] = release["version"]
    images: dict[str, Any] = {"image": {"digests": {}}}
    for name in ("api", "dashboard"):
        repository, sha = release["images"][name].split("@")
        images["image"][name] = repository
        images["image"]["digests"][name] = sha
    outputs = {"application.json": app, "images.json": images, "release.json": release}
    for filename, value in outputs.items():
        write(target / filename, value)
    return [target / name for name in outputs]


def gh_json(endpoint: str) -> Any:
    return json.loads(subprocess.check_output(["gh", "api", endpoint], text=True))


def check_environment(environment: str) -> None:
    document = gh_json(f"repos/{REPO}/environments/{environment}")
    rules = document.get("protection_rules", [])
    reviewers = [r for r in rules if r.get("type") == "required_reviewers"]
    if (
        not reviewers
        or not reviewers[0].get("reviewers")
        or not reviewers[0].get("prevent_self_review")
    ):
        raise ValueError("Configure independent required reviewers and prevent self-review")
    if document.get("can_admins_bypass", True):
        raise ValueError("Disable administrator bypass for the environment")
    if document.get("deployment_branch_policy") != {
        "protected_branches": False,
        "custom_branch_policies": True,
    }:
        raise ValueError("Configure custom deployment branch policy")
    policies = gh_json(f"repos/{REPO}/environments/{environment}/deployment-branch-policies")
    allowed = policies.get("branch_policies", [])
    if len(allowed) != 1 or allowed[0].get("name") != "main" or allowed[0].get("type") != "branch":
        raise ValueError("Only the main branch may use this environment")


def check_source(source: str) -> None:
    if not re.fullmatch(r"[a-f0-9]{40}", source):
        raise ValueError("Invalid source commit")
    subprocess.run(["git", "merge-base", "--is-ancestor", source, "origin/main"], check=True)
    pages = json.loads(
        subprocess.check_output(
            [
                "gh",
                "api",
                "--paginate",
                "--slurp",
                f"repos/{REPO}/commits/{source}/check-runs?per_page=100",
            ],
            text=True,
        )
    )
    latest: dict[str, Any] = {}
    for page in pages:
        for check in page["check_runs"]:
            # Only GitHub Actions checks from this repository are accepted.
            if check.get("app", {}).get("slug") == "github-actions":
                prior = latest.get(check["name"])
                if prior is None or check["id"] > prior["id"]:
                    latest[check["name"]] = check
    missing = [
        name
        for name in sorted(REQUIRED_CHECKS)
        if latest.get(name, {}).get("conclusion") != "success"
    ]
    if missing:
        raise ValueError(f"Required source checks not successful: {missing}")


def staging_receipt(release: Any, context: str) -> dict[str, Any]:
    validate_release(release)
    deployments = {}
    for name in ("api", "dashboard", "worker"):
        raw = subprocess.check_output(
            [
                "kubectl",
                "--context",
                context,
                "-n",
                "sentinel-staging",
                "get",
                "deployment",
                "sentinel-" + name,
                "-o",
                "json",
            ],
            text=True,
        )
        item = json.loads(raw)
        spec, status = item["spec"], item.get("status", {})
        expected = release["images"]["api" if name == "worker" else name]
        image = spec["template"]["spec"]["containers"][0]["image"]
        replicas = spec.get("replicas", 1)
        if (
            image != expected
            or replicas < 2
            or status.get("observedGeneration", 0) < item["metadata"]["generation"]
        ):
            raise ValueError("Staging deployment source/generation mismatch")
        if any(
            status.get(k, 0) != replicas
            for k in ("updatedReplicas", "readyReplicas", "availableReplicas")
        ):
            raise ValueError("Staging rollout has not completed")
        deployments[name] = {"image": image, "ready": replicas, "uid": item["metadata"]["uid"]}
    return {
        "status": "verified",
        "namespace": "sentinel-staging",
        "context": context,
        "observed_at": datetime.now(UTC).isoformat(),
        "release_sha256": digest(release),
        "deployments": deployments,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    promotion = sub.add_parser("promote")
    promotion.add_argument("--release", required=True, type=Path)
    promotion.add_argument("--environment", choices=["staging", "production"], required=True)
    source = sub.add_parser("check-source")
    source.add_argument("--source", required=True)
    environment = sub.add_parser("check-environment")
    environment.add_argument("--environment", choices=["staging", "production"], required=True)
    receipt = sub.add_parser("verify-staging")
    receipt.add_argument("--release", required=True, type=Path)
    receipt.add_argument("--context", required=True)
    receipt.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "promote":
        for path in promote(read(args.release), args.environment):
            print(path.relative_to(ROOT))
    elif args.command == "check-source":
        check_source(args.source)
    elif args.command == "check-environment":
        check_environment(args.environment)
    else:
        write(args.output, staging_receipt(read(args.release), args.context))


if __name__ == "__main__":
    main()
