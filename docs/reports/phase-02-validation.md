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

The first Trivy scan step returned nonzero and was advisory. Its report upload was skipped because GitHub excludes hidden directories by default. The workflow now explicitly uploads reports and summarizes all four images. Reports recovered from [run 41476109557](https://github.com/manikantbindass/KubeGuardianAI-Self-Healing-Kubernetes-Cluster-on-AWS-EKS/actions/runs/41476109557) show:

| Image | HIGH | CRITICAL | Findings with a listed fixed version |
| --- | --- | --- | --- |
| API (also worker/migrator) | 114 | 6 | 75 |
| Dashboard | 59 | 7 | 33 |
| PostgreSQL | 93 | 16 | 60 |
| Redis | 57 | 7 | 31 |

These are package/advisory occurrences, not unique CVE totals or a reachability assessment. They include base OS and packaged runtime findings. The Trivy JSON artifacts retain package versions, advisory IDs, fixed versions where available and image metadata. Scanning is advisory in this development workflow, so a successful job does **not** mean clean images. This PR remains draft for image-security follow-up: update reviewed base/runtime/store versions, rebuild and rescan, triage remaining findings with evidence, then pin approved digests before production. Do not suppress findings or infer that non-root execution removes vulnerable code.

The later [run 41476207732](https://github.com/manikantbindass/KubeGuardianAI-Self-Healing-Kubernetes-Cluster-on-AWS-EKS/actions/runs/41476207732) also passed cluster bootstrap and live tests including the stronger DNS-aware isolation test, Redis outage readiness=503 while liveness remains healthy, Redis recovery, and actual frontend smoke. Scan results remain advisory and must be checked separately.

No metrics-server is installed by default, so HPA load response is not tested. Ingress templates validate, but no ingress controller/TLS deployment was exercised; local access uses loopback port-forward. Dev/prod profiles require external stores and reviewed egress/ingress allowances and are not production certification. Application dependencies are locked; base image tags are versioned but not digest-pinned. No AWS or real workload remediation is introduced.
