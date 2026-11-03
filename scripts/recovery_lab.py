"""Reproducible, isolated local recovery lab. No AWS or default-context mutations."""

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLUSTER = "kubesentinel-recovery"
CONTEXT = "kind-" + CLUSTER
NAMESPACE = "sentinel-lab"


def run(*args: str, data: str | None = None, cwd: Path = ROOT) -> str:
    result = subprocess.run(
        args, input=data, text=True, capture_output=True, cwd=cwd, timeout=900, check=False
    )
    if result.returncode:
        raise RuntimeError(f"{args[0]} exited {result.returncode}: {result.stderr[-5000:]}")
    return result.stdout


def kube(*args: str, data: str | None = None) -> str:
    return run("kubectl", "--context", CONTEXT, "-n", NAMESPACE, *args, data=data)


def generate() -> None:
    run(
        "go",
        "run",
        "sigs.k8s.io/controller-tools/cmd/controller-gen@v0.20.1",
        "object",
        "paths=./api/v1alpha1",
        "crd:crdVersions=v1",
        "output:crd:artifacts:config=crds",
        cwd=ROOT / "operator",
    )
    destination = ROOT / "infrastructure/helm/recovery-operator/crds"
    destination.mkdir(parents=True, exist_ok=True)
    for path in (ROOT / "operator/crds").glob("*.yaml"):
        shutil.copyfile(path, destination / path.name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["generate", "bootstrap", "install", "test", "clean"])
    parser.add_argument("--execute", action="store_true", help="explicitly enable lab execution")
    args = parser.parse_args()
    artifact_dir = ROOT / ".cache/operator"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("GOTOOLCHAIN", "go1.26.8")
    os.environ.setdefault("GOCACHE", str(ROOT / ".cache/gobuild"))
    os.environ.setdefault("GOMODCACHE", str(ROOT / ".cache/gomod"))
    if args.action == "generate":
        generate()
        return
    if args.action == "clean":
        print(run("kind", "delete", "cluster", "--name", CLUSTER))
        return
    if args.action == "test":
        print(run("python", "scripts/test_operator.py"))
        return
    if args.action == "bootstrap":
        run("docker", "info")
        if CLUSTER in run("kind", "get", "clusters").splitlines():
            raise SystemExit(
                "Recovery cluster exists. Clean explicitly before creating a fresh lab."
            )
        print(
            run(
                "kind",
                "create",
                "cluster",
                "--name",
                CLUSTER,
                "--image",
                "kindest/node:v1.35.0",
                "--config",
                "operator/testdata/kind.yaml",
                "--wait",
                "180s",
            )
        )
        for image, dockerfile in (
            ("operator", "operator/Dockerfile"),
            ("recovery-demo", "apps/demo-workload/Dockerfile"),
        ):
            print(
                run(
                    "docker",
                    "build",
                    "--pull",
                    "-f",
                    dockerfile,
                    "-t",
                    f"kubesentinel/{image}:phase06-local",
                    ".",
                )
            )
            run(
                "kind",
                "load",
                "docker-image",
                f"kubesentinel/{image}:phase06-local",
                "--name",
                CLUSTER,
            )
    if not (artifact_dir / "approver.key").exists():
        print(run("go", "run", "./cmd/approval", "--command", "keygen", cwd=ROOT / "operator"))
    # Only this dedicated kind context is read. No arbitrary user cluster is targeted.
    service = json.loads(
        run(
            "kubectl",
            "--context",
            CONTEXT,
            "-n",
            "default",
            "get",
            "service",
            "kubernetes",
            "-o",
            "json",
        )
    )
    endpoints = json.loads(
        run(
            "kubectl",
            "--context",
            CONTEXT,
            "-n",
            "default",
            "get",
            "endpoints",
            "kubernetes",
            "-o",
            "json",
        )
    )
    addresses = {service["spec"]["clusterIP"]}
    addresses.update(
        a["ip"] for subset in endpoints.get("subsets", []) for a in subset.get("addresses", [])
    )
    values = {
        "executionEnabled": args.execute,
        "approvalPublicKeys": json.loads((artifact_dir / "public-keys.json").read_text()),
        "apiServerCIDRs": [ip + ("/128" if ":" in ip else "/32") for ip in sorted(addresses)],
    }
    values_path = artifact_dir / "values.json"
    values_path.write_text(json.dumps(values), encoding="utf-8")
    print(
        run(
            "helm",
            "upgrade",
            "--install",
            "sentinel-recovery",
            "infrastructure/helm/recovery-operator",
            "--namespace",
            NAMESPACE,
            "--create-namespace",
            "-f",
            str(values_path),
            "--wait",
            "--timeout",
            "180s",
        )
    )
    print(kube("apply", "-f", "operator/testdata/workload.yaml"))
    print(kube("rollout", "status", "deployment/demo-recovery", "--timeout=120s"))
    print(kube("apply", "-f", "operator/policies/dry-run.yaml"))
    print("Ready: dry-run policy installed. Global execution:", args.execute)


if __name__ == "__main__":
    main()
