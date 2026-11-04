# Evidence-led incident investigation

These are read-only investigation steps. They authorize no Kubernetes mutation. Evidence must refer to the same namespace/workload, a relevant time window and an observed source. A symptom or nearby deployment change is not proof of causation.

## Memory pressure

Inspect termination reasons and container limits. Compare memory working set, RSS where available, node memory pressure and OOM event timestamps. Identify missing samples, throttling and recent workload changes. An OOMKilled incident supports memory investigation, but does not establish a memory leak or justify raising limits automatically. Collect application-level evidence before deciding whether requests, limits, code or traffic are responsible.

## Startup and availability

Inspect readiness/startup probe status, termination reasons, events, desired/ready replicas and rollout conditions. Confirm the exact Deployment identity rather than inferring ownership from a pod name prefix. Compare first failure with preceding rollout/scale events. Inspect sanitized application logs through authorized existing log tooling; this engine does not fetch logs. A crash loop can have many causes, including configuration, dependencies, resource pressure and code errors.

## Latency

Compare p50/p95/p99 and error-rate windows with traffic and baseline conditions. Check dependency health, saturation, missing samples and deployment changes. A metric anomaly record is evidence of detector output, not a calibrated probability of a root cause. Use [observability](observability.md) for actual query and collection configuration.

## Evidence collection

Confirm namespace/workload, cluster context, source timestamps and telemetry freshness. Identify which data is absent. Keep secrets/PII out of notes and exported evidence. When a reason has no supported runbook mapping, collect evidence instead of guessing an action. Record operator feedback as supported, unsupported or insufficient-evidence. Feedback is an annotation, never an approval.

For any eventual recovery, use the independently governed [operator workflow](recovery-operator.md): policy evaluation, scoped allowlists, signed approvals where required, cooldowns, budgets and verification. This runbook provides no execution bypass.
