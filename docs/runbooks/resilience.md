# Phase 09 scalability and resilience

Implemented improvements: bounded SQL queue admission (default 1,000 queued greeting jobs), PostgreSQL transaction-scoped advisory lock across API replicas, composite `(status, created_at)` index, configurable per-process pool ceiling, and an opt-in two-replica lab profile with CPU HPA stabilization. API HPA no longer competes with a fixed API replica count in Git. Apply migration `0005_queue_index` before rollout. Index creation is transactional and can block writes on a large existing table; schedule a maintenance window or prepare a separately reviewed concurrent-index migration.

## Queue and database behavior

PostgreSQL is the durable queue; Redis is only a bounded wake-up hint/cache. This avoids a dual-write correctness dependency on Redis Streams. Workers use `FOR UPDATE SKIP LOCKED` and commit the deterministic greeting result in one transaction, so multiple worker replicas can claim distinct jobs. A worker crash rolls back its unfinished transaction. Redis loss delays polling but does not discard committed SQL jobs. Database loss prevents acceptance/processing; readiness fails. Authentication-dependent operations continue to fail closed during Redis rate-limiter failure.

The queue admission advisory lock is transaction-scoped and protected by the existing three-second statement timeout. Saturation returns 429 and `Retry-After: 2`; lock/database saturation returns a sanitized service error rather than accumulating unbounded work. SQLite unit tests exercise the limit, **not** PostgreSQL cross-process locking. PostgreSQL migration/concurrency behavior requires the real integration environment. Greeting storage is still retained after completion; operators must implement retention/archival before prolonged write-load tests. The limit applies to greeting jobs, not every incident or remediation outbox.

Pool size defaults to five plus two overflow connections, with pre-ping, three-second acquisition/connect/statement bounds and 30-minute recycle. Budget `API processes * (pool_size + overflow) + worker processes * (pool_size + overflow) + migration/bridge/monitoring connections` below PostgreSQL capacity with administration headroom. Add PgBouncer transaction pooling only after testing prepared statements/session assumptions. Do not increase replicas without this calculation. Worker SIGTERM completes the current bounded SQL operation before its loop exits; existing Redis/DB retry waits are two seconds. There is no general-purpose external-side-effect retry/dead-letter queue or distributed operations bridge claim mechanism; keep one logical bridge worker.

## Scheduling and node capacity

`values-resilience.yaml` opts into two API/dashboard/worker replicas, resource limits and API HPA 2–4 replicas. It requires metrics-server; HPA scale-up is bounded and scale-down stabilizes for five minutes. CPU is a starting signal, not a database/queue-lag SLO. Worker/dashboard autoscaling and backlog-based KEDA scaling remain unimplemented. Existing API PDB permits at most one unavailable replica; there is no promise that a PDB prevents involuntary failures or provides zone redundancy. Extend PDBs/topology distribution after evaluating stateful dependencies and available nodes. The resource quota example is administrator-owned and must be applied with an explicit disposable namespace.

For EKS managed node groups, use Cluster Autoscaler with namespace/resource/IAM limits and the existing Terraform min/max bounds; install it only after cost approval. Karpenter is an alternative when provisioning latency and heterogeneous workloads justify more operational complexity. Do not let Terraform continually reset desired capacity while an autoscaler owns it. This phase installs neither autoscaler nor paid nodes. See [Kubernetes HPA](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/) and [node autoscaling](https://kubernetes.io/docs/concepts/cluster-administration/node-autoscaling/).

## Repeatable load tests

Windows and Linux/macOS use the same Python harness after `uv sync --frozen`:

```bash
uv run python scripts/benchmark_http.py --start-api --output .cache/benchmarks/http
uv run pytest -m "not postgres" -q
helm lint infrastructure/helm/kubesentinel -f infrastructure/helm/kubesentinel/values-resilience.yaml
```

The harness starts the real FastAPI application on isolated loopback port 18090, warms readiness of the **health endpoint only**, then records 100 requests per trial, three repetitions at each concurrency 1/4/8. It writes raw CSV and summary JSON with source/dirty-tree provenance and terminates its own process. It rejects non-loopback URLs. Results do not measure PostgreSQL, dashboard rendering, scoring, policy throughput or recovery. Install the pinned optional ML plotting dependency group to regenerate charts; the committed chart was generated with Matplotlib from observed summaries.

For an explicitly authorized local test target with k6 installed:

```bash
# POSIX environment syntax; PowerShell: $env:AUTHORIZED_TARGET='true', etc.
AUTHORIZED_TARGET=true k6 run --out json=.cache/k6-raw.json --summary-export=.cache/k6-summary.json tests/load/api.js
# WRITE_LOAD=true additionally writes synthetic greeting jobs: use a disposable database.
# Generic scoring/incident ingress accepts an operator-prepared schema-valid synthetic fixture:
AUTHORIZED_TARGET=true ENDPOINT=http://127.0.0.1:8000/api/v1/internal/events PAYLOAD_FILE=./event.json TOKEN=LOCAL_TEST_TOKEN k6 run tests/load/ingestion.js
```

Use a protected environment variable for the token; never put a real token into shell history, fixtures or results. The same ingestion runner can target `/api/v1/score` on the detector with a scoring fixture. Reusing one incident identity tests deduplication; generate distinct event identities for insert-load experiments. Validate fixtures at low rate first. k6 thresholds (1% errors, 500 ms API/dashboard p95, 1,000 ms ingest p95) are provisional test budgets, not established product SLOs. k6 requires an explicit authorization variable even for reads. Its HTTP dashboard request does not measure browser rendering/Web Vitals. See [k6 thresholds](https://grafana.com/docs/k6/latest/using-k6/thresholds/).

## Destructive chaos authorization and isolation

**No destructive chaos was executed in this phase.** Obtain explicit authorization for the named scenario, cluster, namespace, time window and cleanup first. A CLI flag records operator intent but is not a substitute for that approval. Do not target a shared kind cluster, production, kube-system or an AWS cluster. `chaos_lab.py` hardcodes `kind-kubesentinel-resilience` and `sentinel-chaos`, requires namespace label `sentinel.ai/disposable=true`, target label `sentinel.ai/fault-target=true`, and `--authorize-destructive`. It supports scoped pod termination, an intentionally invalid demo rollout image, and draining only workers with the dedicated kind cluster name prefix. It never permits control-plane drain or forced pod deletion. Test the guards before any authorized execution; these destructive code paths have not been live-certified.

Create a fresh dedicated kind cluster with at least two workers, deploy only isolated synthetic targets and apply the labels through an administrator. Record manifests, image digests, node names and namespace UID. Capture pre-fault readiness, metrics, incidents and audit. Example after approval:

```bash
uv run python scripts/chaos_lab.py terminate-pod --target APPROVED_POD --authorize-destructive
uv run python scripts/chaos_lab.py rollout-failure --target APPROVED_DEPLOYMENT --authorize-destructive
uv run python scripts/chaos_lab.py node-drain --target kubesentinel-resilience-worker --authorize-destructive
```

Rollback invalid rollouts with the **same explicit context/namespace** and a reviewed prior revision. Uncordon the drained worker. Verify resource health and absence of unexpected actions, then delete only the dedicated disposable cluster after reviewing the target. Never use broad cleanup against a computed/unknown context.

| Scenario | Controlled procedure and evidence required | Execution status |
| --- | --- | --- |
| CrashLoopBackOff / OOMKilled | Opted-in synthetic workload with bounded crash/memory fault; record exit reason, restart delay and node pressure | Not run |
| Pod termination / failed rollout / drain | Guarded harness above, then readiness and rollback verification | Not run |
| Prometheus outage | Stop isolated monitoring service; verify truthful unavailable state, continued health and restored queries | Not run in Phase 09 |
| Redis/PostgreSQL outage | Isolated Compose stop/start, committed-job count, cache/auth fail-closed behavior and backlog drain | Not run in Phase 09 |
| API server unavailability | Inject failing Kubernetes client transport into controller tests; never disable a shared API server | Existing operator tests, no new live experiment |
| Latency/packet loss | Separately approved namespace-scoped network fault tool; bound duration and privileges, predeclare cleanup | Tool integration not implemented |

## Measurement and comparison protocol

For native versus Sentinel recovery, hold Kubernetes probes/controllers, image digests, replicas, requests/limits and fault seed constant. Use independent disposable clusters or fully reset trials, randomized order and at least five paired repetitions per fault. Do not attribute native restarts to Sentinel. Sentinel must remain dry-run until a separate execution approval; count an action as recovery only after existing verification criteria pass. Record every failed trial and timeout. Compare capability-appropriate cases: native Kubernetes restarts containers, whereas a signed policy action can change a deployment's allowed scale; they are not identical interventions.

Export per-trial JSON/CSV with environment, nodes, test duration, repetitions, incident/fault identity, fault/detection/action/verification timestamps, p50/p95/p99, requests/errors, CPU/memory, SQL query/pool saturation, queue count/oldest age and desired/ready replicas. Compute detection delay from fault-to-detection, initiation delay from detection-to-action, verification duration from action-to-verified, and false remediation rate using independently labeled safe/unsafe outcomes. Missing values stay null; do not treat them as zero. Calculate availability over a defined window and exclude neither outage periods nor failed trials. Existing fixed-query Prometheus access and route-template labels bound metric dimensions; never label metrics by incident ID or raw URL. Queue/SQL saturation and policy throughput dashboards still need instrumentation.

## Backup and recovery

Before writes/faults, use encrypted PostgreSQL backups, WAL archiving/PITR where supported, separate backup credentials/storage and documented retention. Restore into a new isolated database, apply supported migrations, verify row/audit counts and application readiness, then explicitly approve cutover. Record measured RPO/RTO after an actual restore; none are established here. Redis cache may be rebuilt, but rate-limit outage must not bypass auth and worker hints must not replace SQL. Existing operator leases/idempotency, approvals, budgets and cooldowns remain authoritative; never introduce an ML/benchmark execution bypass.

## Observed evidence and limits

[Raw CSV](../benchmarks/phase-09/loopback/raw.csv), [summary JSON](../benchmarks/phase-09/loopback/summary.json) and [latency chart](../benchmarks/phase-09/loopback/latency.png) contain one Windows host's actual 900 loopback health requests. All returned HTTP 200. Trial p95 ranged approximately 16.6–31.0 ms. These short closed-loop runs have shared-host scheduling/connection overhead, no database traffic, no confidence intervals and no saturation search; do not generalize their throughput to deployments or claim a recovery improvement.

Phase 09 remains incomplete for live-cluster scalability/chaos acceptance: local Docker is unavailable, destructive authorization has not been supplied, and k6, scoring/policy load, database saturation, native-vs-Sentinel recovery, overhead and SLO measurements have not been executed. Phase 08 image vulnerability gates also remain release blockers. This document distinguishes delivered harnesses and code changes from unmeasured reliability claims.
