# Local Kubernetes deployment

Phase 02 provides Helm templates and a scoped kind lifecycle, not AWS infrastructure. The API remains unauthenticated; use a trusted local lab. Docker Desktop must run Linux containers. This host currently has no Docker engine, so local cluster and image scans are blocked; consult the Local Kubernetes CI workflow for live results, rather than inferring success from templates.

## Prerequisites and bootstrap

Install Python 3.12+, Docker, kubectl, kind 0.31.0 and Helm 3.19.0. Scripts work from repository root on Windows PowerShell and Linux/macOS. On Windows use `py -3.12` instead of `python3`, and add installed tool directories to PATH. Select the Linux Docker context deliberately if necessary (`$env:DOCKER_CONTEXT='desktop-linux'` or `export DOCKER_CONTEXT=desktop-linux`). The script does not change global kubeconfig context.

```sh
python3 scripts/kubernetes.py bootstrap --tag phase02
python3 scripts/kubernetes.py test --tag phase02
kubectl --context kind-kubesentinel -n kubesentinel port-forward service/sentinel-dashboard 3100:3000
```

In another terminal forward API port `8100:8000` from `service/sentinel-api`, then run `python3 scripts/setup/smoke.py --dashboard http://127.0.0.1:3100 --api http://127.0.0.1:8100`. Open the dashboard on localhost:3100. Port-forward is the default local access method; no ingress controller is installed automatically.

Bootstrap refuses an existing named cluster, creates a two-node kind lab using Kubernetes 1.35.0, creates the namespace and random local credentials, builds explicitly tagged images using frozen npm/uv locks, loads them into kind, and waits for Helm rollout. A migration Job runs on each Helm release revision; API readiness waits for its schema. Database PVCs retain data across pod restarts. Cluster deletion destroys local volumes and all lab data. This is local persistence, not managed database durability.

```sh
python3 scripts/kubernetes.py build --tag phase02
python3 scripts/kubernetes.py scan --tag phase02
python3 scripts/kubernetes.py clean
```

Scan requires Trivy on PATH and a running Docker engine. CI stores JSON application-image reports even when HIGH/CRITICAL vulnerabilities are found; scan failure is advisory and must be reviewed before any production promotion. No clean scan is claimed without a report. Build contexts exclude environment files, Git metadata, caches and unrelated project areas. Application containers have numeric non-root users, read-only filesystems, restricted capabilities, runtime-default seccomp and bounded temporary volumes. Official local datastore images retain their own entrypoint/ownership behavior and are not claimed as fully hardened production stores. Tags and locks give repeatable dependency selection; base tags are not immutable digests and bit-identical builds are not guaranteed.

## Chart reference

Canonical manifests live in `infrastructure/helm/kubesentinel/templates`; the standalone namespace manifest lives under `infrastructure/kubernetes`. Do not maintain duplicate rendered resources. Render with `helm template sentinel infrastructure/helm/kubesentinel --namespace kubesentinel`. Run `helm lint` and `helm template` for local/dev/prod values; CI also runs kubeconform strict schema validation.

| Value | Meaning |
| --- | --- |
| `image.api`, `image.dashboard`, `image.tag`, `image.pullPolicy` | Explicit local repositories/tag; use a unique commit tag for subsequent releases |
| `secretName` | Existing Secret, never secret values in Helm: DATABASE_URL, REDIS_URL, POSTGRES_PASSWORD |
| `localStores` | Disposable local PostgreSQL/Redis with 1Gi PVCs; false in dev/prod profiles |
| `replicas`, `resources` | App replicas and CPU/memory requests/limits |
| `ingress` | Optional existing controller/class/host; default disabled |
| `pdb.enabled` | API disruption budget for multi-replica configurations; not enabled for one replica |
| `autoscaling` | CPU HPA; enable only after installing a working metrics API |
| `observability.annotations` | Pod annotations; no metrics endpoint or monitoring stack is fabricated |

Dev/prod values are starting profiles, not production-ready deployments. Supply external stores, credentials, network egress policy, identity, TLS, backups and image review before use. Local network isolation permits only app-labelled namespace peers and kube-dns. An external datastore or ingress controller requires separately reviewed NetworkPolicy allowances; simply enabling ingress is insufficient. Never open unrestricted egress to make a failed deployment green.

Metrics-server is unnecessary for the default replica count and is not installed. To exercise HPA, explicitly install a reviewed metrics-server version compatible with the cluster, validate `kubectl top pods`, then enable autoscaling with minimum two replicas. kind may require a local-only kubelet certificate override; do not copy that setting into production. HPA behavior is unverified until metrics are actually available.

## Verification and troubleshooting

The test script checks service DNS from the dashboard, API readiness, API restart, two replicas, rollout/undo and RBAC. A separate unlabeled pod must fail to connect to the API, checking policy enforcement rather than only policy presence. kind must provide a NetworkPolicy-enforcing networking implementation; if that negative test succeeds in connecting, stop and fix CNI enforcement. App service accounts have no API permissions or mounted token. A separate observer can get only named deployments and cannot mutate workloads.

For manual rollout use `kubectl --context kind-kubesentinel -n kubesentinel rollout status deployment/sentinel-api`, `rollout restart`, `rollout undo` and `scale deployment/sentinel-api --replicas=2`. Run smoke after each operation; schema changes must remain compatible with rollback. Do not assume Helm rollback reverses database migrations.

- Docker pipe/socket errors: start a Linux engine before kind; installation of the client alone is insufficient.
- ImagePullBackOff: load exactly the chart tag into the named kind cluster; verify repository names and pull policy.
- Pending PVC: inspect storage classes and local provisioner; do not discard existing volumes to repair a rollout.
- API not ready: inspect migration Job logs, Secret keys and database DNS. Liveness deliberately does not depend on PostgreSQL/Redis.
- Network failure: inspect labels, namespace and NetworkPolicies; check kube-dns and CNI enforcement.
- Reusing lab: cleanup deletes only the explicitly named kind cluster. No global prune, account-wide deletion or AWS operation is used.
