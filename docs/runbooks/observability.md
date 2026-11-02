# Phase 04 observability

Local, trusted kind lab only. Prometheus, kube-state-metrics, Alertmanager, Loki, Grafana and OpenTelemetry Collector are defined in the separate `infrastructure/helm/observability` chart. No AWS integration is enabled or provisioned. The API remains a local development service; do not publish these endpoints or Grafana anonymously on the internet.

## Start and verify

```sh
python3 scripts/kubernetes.py bootstrap --tag phase04 --observability
npm ci
npx playwright install chromium
python3 scripts/test_observability.py
```

On Windows use `py -3.12` and a running Linux Docker engine, kind 0.31.0, Helm 3.19.0 and kubectl on PATH. Bootstrap creates a random ingestion token in the runtime Secret and a separate `sentinel-grafana` administrator Secret; neither is stored in Git or printed. The Event collector receives only the ingestion token, and Alertmanager mounts only that key. Bootstrap resolves Kubernetes service/endpoint IPs into narrow API egress rules. Helm waits for the app migration and telemetry workloads. Default startup without `--observability` leaves metrics ingestion disabled unless explicitly configured.

For interactive use: `kubectl --context kind-kubesentinel -n kubesentinel port-forward service/grafana 3300:3000`, then open localhost:3300. Viewer-only anonymous access is a deliberate lab setting. Prometheus 9090, Loki 3100 and Alertmanager 9093 remain ClusterIP services; forward only to loopback when debugging. Cleanup: `python3 scripts/kubernetes.py clean`, which deletes only the named kind cluster and its local data.

The acceptance script generates bounded HTTP requests and one 32MiB-memory OOM Deployment named `sentinel-fault`. It refuses to overwrite an existing fixture, verifies genuine OOM/state metrics, actual Kubernetes Warning ingestion, Alertmanager silence/unsilence/resolution, Loki log queries, OTLP span reception, persisted incidents during a Prometheus outage, and captures all six provisioned Grafana dashboards. It cleans the fixture and port-forward processes. Never run faults against production. Run only in this named isolated lab.

## Signals and data paths

- API `/metrics`: Prometheus counters/histograms label only method, route template and HTTP status. Raw path IDs, trace IDs, user names, event UIDs and request bodies are not metric labels. CPU/memory comes from real kubelet cAdvisor; kube-state-metrics exposes readiness/restarts/OOM/node pressure/capacity/deployment replicas.
- JSON API request logs contain correlation/trace/span IDs and route templates. The node Collector reads **only API container log paths** and ships OTLP logs to Loki. It runs in a separate telemetry namespace because read-only host log mounts require a Pod Security exception; no privileged mode, host network or Kubernetes API token is used. Root inside that collector can read mounted host logs: this is an explicit local-lab risk, not a claim of production isolation.
- API spans use bounded asynchronous OTLP HTTP export to the Collector. Collector accepts spans and emits diagnostic summaries; no durable trace backend or trace-search UI is claimed. Loki retains trace IDs embedded in request JSON for correlation.
- A separate read-only namespaced Event collector polls core/v1 events and sends Warning events using a shared Bearer token. Normal scheduling noise is ignored. Kubernetes events expire at the server; polling is best-effort, with retries and PostgreSQL deduplication, not a guaranteed event archive.
- Prometheus evaluates recording/alert rules, Alertmanager groups/deduplicates/silences/inhibits notifications, then authenticates webhooks into the API. Persisted incidents outlive Prometheus outages. Telemetry health is separate from API process health and database readiness.

## Incident contract and API

Migration `0002_incidents` creates a unique fingerprint, source, namespace/resource, reason/summary, severity/status, occurrence count and first/last/event times. Kubernetes identity uses namespace + event UID; alert identity uses alert name + namespace + workload + episode start. Resource versions/counts are evidence, not public metric labels. Duplicate/retried notifications update one record; old firing notifications cannot reopen a later resolved record. Concurrent inserts use a unique constraint and row lock retry. A new alert episode has a new start time and record. No remediation executes from ingestion.

`GET /api/v1/incidents?limit=50` returns at most 100 records; the dashboard shows real persisted rows with loading/empty/error states. `POST /api/v1/internal/events` and `/internal/alerts` require `Authorization: Bearer TELEMETRY_TOKEN`; empty configuration disables ingestion. Payloads have field/batch limits. Collection is restricted to `kubesentinel`. Read APIs remain unauthenticated local-only; a future product authorization layer is required before exposure. Event messages can contain sensitive workload text: retain only reviewed telemetry and never send real production secrets into this lab.

`GET /api/v1/metrics/{cpu|memory|restarts|request_rate|error_rate}` executes a fixed server-side query with a three-second timeout, not arbitrary client PromQL. Missing Prometheus returns a sanitized 503; incident reads and liveness continue. `GET /api/v1/telemetry/health` checks the API scrape target, not full end-to-end health. Successful scrape alone does not prove every log, event or alert path.

## Dashboards, rules and SLO

Six JSON dashboards are provisioned: cluster overview; namespace/workload; application performance; incident/log timeline; recovery history; SLO/error budget. Recovery counters are initialized zero and labelled as an unimplemented executor contract. No fabricated action history is inserted. SLO is a proposed 99.9% non-5xx request objective with p95 <300ms. Health/readiness/metrics requests are excluded from HTTP SLI counters. Short windows and seven-day retention cannot prove 30-day compliance. The 14.4× dual-window error-budget alert is a diagnostic starting point, not a validated paging policy.

Rules cover missing API scraping, unavailable replicas, container restarts, OOMKilled, long Pending and node pressure. Severity is info/warning/critical; unrecognized severities normalize to warning. Alertmanager grouping keys exclude transport replica IDs. Silence handling stays in Alertmanager; suppressed alerts do not create incidents, while already-open incidents remain evidence until resolution. No external notification recipient is configured.

PromQL examples:

```promql
sum(rate(container_cpu_usage_seconds_total{namespace="kubesentinel",container!=""}[5m]))
sum(container_memory_working_set_bytes{namespace="kubesentinel",container!=""})
kube_pod_container_status_restarts_total{namespace="kubesentinel"}
kube_pod_container_status_last_terminated_reason{namespace="kubesentinel",reason="OOMKilled"}
kube_deployment_status_replicas_available{namespace="kubesentinel"}
histogram_quantile(0.95, sum by(le) (rate(sentinel_http_duration_seconds_bucket[5m])))
sum by(source,severity,status) (sentinel_incidents)
```

## Retention, cardinality and security

Prometheus retains seven days or 1GB, with a 2GiB default PVC. Loki filesystem/TSDB retains seven days via compactor. Grafana and Alertmanager use local PVCs; Alertmanager data retention is 120 hours. Collector queues/offsets are bounded local ephemeral storage, so restarts can replay logs; Loki ingestion is not exactly once. Increase PVC size/retention deliberately for longer experiments. KSM namespace/resource selection and scrape sample limits bound collection; known identity labels are dropped where they are unnecessary. Incident SQL retention is not automatic in this phase: review/delete/export using an approved data-retention procedure before long-lived use.

Prometheus has read access to node discovery and GET node proxy **for the two named kind nodes**. Kubernetes node-proxy access is sensitive; it is not app RBAC and must be reviewed before cloud use. KSM has read-only object access, and the event collector can read only namespace events. API pod tokens remain disabled. Monitoring workloads communicate through labelled namespace peers plus narrow Kubernetes API/DNS and cross-namespace Collector rules. Kubernetes NetworkPolicy is not an HTTP authentication system.

Optional CloudWatch integration remains the Phase 03 log-group/Pod Identity infrastructure contract only. No CloudWatch exporter or paid resources are enabled here. A future ADOT/CloudWatch exporter needs explicit region/identity, egress/retention/cost approval and separate tests.

## Troubleshooting

- Missing API metrics: inspect `/metrics`, Prometheus `/targets`, app readiness/schema migration and NetworkPolicy selectors.
- Missing cluster metrics: inspect KSM resources/RBAC and Prometheus node-proxy names; do not grant cluster-admin to fix scraping.
- Missing logs: check telemetry DaemonSet scheduling, read-only host path, filelog parser errors, Loki readiness and OTLP endpoint `/otlp`. The Collector excludes its own logs to avoid loops.
- Missing trace IDs: ensure API OTLP endpoint is configured and the Collector receives spans. Trace export outage must not make the API unavailable.
- Missing incidents: verify token keys match, event collector Role, Alertmanager route/silences, API logs and database migration. Do not log Bearer tokens or full Secret objects.
- Grafana empty panels: verify datasource health and time range; empty recovery history is intentional. Screenshots are evidence only when captured from a real successful run.
- Storage full: inspect PVC use and retention; do not drop evidence or increase cardinality without review. Single-replica local stores do not provide HA.
