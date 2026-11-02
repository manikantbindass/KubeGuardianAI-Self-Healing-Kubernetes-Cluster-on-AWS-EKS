# Phase 02 validation

Local environment: Windows, Docker client installed but no reachable engine. The kind create attempt failed before creating a cluster. No AWS resources were created. Numeric non-root image users, runtime security contexts, resource/probe settings, local persistence and namespace/RBAC/network policy are defined in the chart.

## Observed results

- Helm 3.19.0 lint/template passed for local, dev and prod profiles.
- kubeconform 0.7.0 strict validation: 18 local resources, 13 dev, 13 prod, and 21 with optional ingress/HPA/PDB enabled; zero invalid/errors/skips.
- Ruff/format and strict mypy passed; backend regression tests: 9 passed, 1 migration test skipped locally.
- Markdown lint, local file links, original LICENSE and six Mermaid syntax checks passed.
- Animated README SVG assets parse as XML and each contains two looping animations. GitHub rendering was not visually inspected.
- [Linux kind CI run 41475077276](https://github.com/manikantbindass/KubeGuardianAI-Self-Healing-Kubernetes-Cluster-on-AWS-EKS/actions/runs/41475077276) passed fresh two-node cluster bootstrap, real image builds/loads, Helm rollout, service DNS, API readiness, API restart, scaling, rollout/undo, RBAC, negative network-isolation test, actual frontend greeting smoke, and cluster cleanup.
- Foundation checks in the same PR passed frontend lint/types/tests/build, backend checks on Linux/Windows, PostgreSQL migrations and Compose smoke.

## Scan follow-up and limits

The first Trivy scan step returned nonzero and was advisory. It is **not a clean scan**. Its report upload was skipped because GitHub excludes hidden directories by default; the workflow now explicitly includes the report files and summarizes all four app/datastore images. Consult the latest PR artifacts and summary before accepting image security.

No metrics-server is installed by default, so HPA load response is not tested. Ingress templates validate, but no ingress controller/TLS deployment was exercised; local access uses loopback port-forward. Dev/prod profiles require external stores and reviewed egress/ingress allowances and are not production certification. Application dependencies are locked; base image tags are versioned but not digest-pinned. No AWS or real workload remediation is introduced.
