"""Cross-platform, explicitly scoped kind development lifecycle. No AWS operations."""

import argparse
import base64
import json
import secrets
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLUSTER = "kubesentinel"
CONTEXT = "kind-kubesentinel"
NAMESPACE = "kubesentinel"


def run(*args: str, data: str | None = None) -> str:
    return subprocess.run(
        args, cwd=ROOT, input=data, text=True, check=True, capture_output=True
    ).stdout


def kube(*args: str, data: str | None = None) -> str:
    return run("kubectl", "--context", CONTEXT, "-n", NAMESPACE, *args, data=data)


def build(tag: str) -> None:
    for component in ("api", "dashboard"):
        print(
            run(
                "docker",
                "build",
                "--pull",
                "-f",
                f"apps/{component}/Dockerfile",
                "-t",
                f"kubesentinel/{component}:{tag}",
                ".",
            )
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "bootstrap", "test", "scan", "clean"])
    parser.add_argument("--tag", default="phase02")
    args = parser.parse_args()
    if args.action == "clean":
        print(run("kind", "delete", "cluster", "--name", CLUSTER))
    elif args.action == "build":
        build(args.tag)
    elif args.action == "scan":
        for image in (
            f"kubesentinel/api:{args.tag}",
            f"kubesentinel/dashboard:{args.tag}",
            "postgres:17.10-bookworm",
            "redis:8.2.2-bookworm",
        ):
            print(run("trivy", "image", "--exit-code", "1", "--severity", "HIGH,CRITICAL", image))
    elif args.action == "bootstrap":
        run("docker", "info")
        clusters = run("kind", "get", "clusters").splitlines()
        if CLUSTER in clusters:
            raise SystemExit("Named cluster exists; run clean explicitly before bootstrapping.")
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
                "infrastructure/kind/cluster.yaml",
                "--wait",
                "180s",
            )
        )
        kube("apply", "-f", "infrastructure/kubernetes/namespace.yaml")
        password = secrets.token_hex(24)
        values = {
            "POSTGRES_PASSWORD": password,
            "DATABASE_URL": f"postgresql+psycopg://sentinel:{password}@sentinel-postgres:5432/sentinel",
            "REDIS_URL": "redis://sentinel-redis:6379/0",
        }
        secret = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": "sentinel-runtime"},
            "data": {
                key: base64.b64encode(value.encode()).decode() for key, value in values.items()
            },
        }
        kube("apply", "-f", "-", data=json.dumps(secret))
        build(args.tag)
        for component in ("api", "dashboard"):
            run(
                "kind",
                "load",
                "docker-image",
                f"kubesentinel/{component}:{args.tag}",
                "--name",
                CLUSTER,
            )
        print(
            run(
                "helm",
                "upgrade",
                "--install",
                "sentinel",
                "infrastructure/helm/kubesentinel",
                "--kube-context",
                CONTEXT,
                "--namespace",
                NAMESPACE,
                "--set-string",
                f"image.tag={args.tag}",
                "--wait",
                "--timeout",
                "8m",
            )
        )
    else:
        for component in ("api", "dashboard", "worker"):
            kube("rollout", "status", f"deployment/sentinel-{component}", "--timeout=180s")
        # Exec in the actual dashboard: checks service DNS and frontend-to-backend health.
        probe = "fetch('http://sentinel-api:8000/api/v1/ready').then(r=>{if(!r.ok)process.exit(1)})"
        kube("exec", "deployment/sentinel-dashboard", "--", "node", "-e", probe)
        kube("scale", "deployment/sentinel-redis", "--replicas=0")
        unavailable = (
            "(async()=>{for(let i=0;i<30;i++){"
            "let r=await fetch('http://sentinel-api:8000/api/v1/ready');"
            "if(r.status===503)return;await new Promise(r=>setTimeout(r,1000));}"
            "process.exit(1)})().catch(()=>process.exit(1))"
        )
        try:
            kube("exec", "deployment/sentinel-dashboard", "--", "node", "-e", unavailable)
            kube(
                "exec",
                "deployment/sentinel-dashboard",
                "--",
                "node",
                "-e",
                "fetch('http://sentinel-api:8000/api/v1/health')"
                ".then(r=>{if(!r.ok)process.exit(1)})",
            )
        finally:
            kube("scale", "deployment/sentinel-redis", "--replicas=1")
        kube("rollout", "status", "deployment/sentinel-redis", "--timeout=180s")
        kube("rollout", "status", "deployment/sentinel-api", "--timeout=180s")
        kube("rollout", "restart", "deployment/sentinel-api")
        kube("rollout", "status", "deployment/sentinel-api", "--timeout=180s")
        kube("scale", "deployment/sentinel-api", "--replicas=2")
        kube("rollout", "status", "deployment/sentinel-api", "--timeout=180s")
        kube("set", "env", "deployment/sentinel-api", "ROLLOUT_TEST=1")
        kube("rollout", "status", "deployment/sentinel-api", "--timeout=180s")
        kube("rollout", "undo", "deployment/sentinel-api")
        kube("rollout", "status", "deployment/sentinel-api", "--timeout=180s")
        kube("scale", "deployment/sentinel-api", "--replicas=1")
        identity = f"system:serviceaccount:{NAMESPACE}:sentinel"
        denied = subprocess.run(
            [
                "kubectl",
                "--context",
                CONTEXT,
                "-n",
                NAMESPACE,
                "auth",
                "can-i",
                "get",
                "deployments",
                "--as",
                identity,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert denied.returncode == 1 and denied.stdout.strip() == "no"
        assert (
            kube(
                "auth",
                "can-i",
                "get",
                "deployment/sentinel-api",
                "--as",
                f"system:serviceaccount:{NAMESPACE}:sentinel-observer",
            ).strip()
            == "yes"
        )
        negative = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {"name": "isolation-probe"},
            "spec": {
                "restartPolicy": "Never",
                "containers": [
                    {
                        "name": "probe",
                        "image": f"kubesentinel/api:{args.tag}",
                        "command": [
                            "python",
                            "-c",
                            "import socket,sys\n"
                            "host=socket.gethostbyname('sentinel-api')\n"
                            "try: socket.create_connection((host,8000),3)\n"
                            "except OSError: sys.exit(0)\nsys.exit(1)",
                        ],
                    }
                ],
            },
        }
        kube("delete", "pod", "isolation-probe", "--ignore-not-found")
        kube("apply", "-f", "-", data=json.dumps(negative))
        kube(
            "wait",
            "--for=jsonpath={.status.phase}=Succeeded",
            "pod/isolation-probe",
            "--timeout=45s",
        )
        kube("delete", "pod", "isolation-probe")
        print("PASS: DNS, API readiness, restart, scaling and rollout/rollback")


if __name__ == "__main__":
    main()
