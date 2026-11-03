# Phase 08 validation

Implemented source/configuration for secure delivery and GitOps. No AWS apply/destroy, paid resources, ECR publication, Sigstore publication or live Argo sync was executed. Existing history and LICENSE are preserved. See [delivery instructions](../runbooks/secure-delivery.md).

## Local checks (Windows)

| Command/check | Observed result |
| --- | --- |
| `python -m pytest -m "not postgres" -q` in locked project environment | 67 passed, one PostgreSQL test deselected; includes 10 new delivery guard tests |
| Ruff check/format and strict mypy | Passed; 69 source files typed |
| `actionlint` v1.7.12 | Passed; all workflow actions SHA-pinned |
| `gitleaks git --redact` v8.30.1 | No leaks after one exact historical non-secret test-idempotency fingerprint exclusion; no directory/rule suppression |
| Checkov 3.4.3, locked separate environment, all Terraform | 139 passed, seven failed findings covered by exact proposed exceptions, no skipped checks/parser errors; [review issue](https://github.com/manikantbindass/KubeSentinel-AI/issues/10), expiry 2026-12-03 |
| `terraform fmt`, `validate` and provider-mocked `test` | Formatted, dev/bootstrap valid; eight mocked tests passed, including environment-bound ECR roles and scoped secret identity |
| `python scripts/validate_delivery.py` in locked security environment | Official Argo schemas passed; staging/production Helm lint and 22 native resources valid; synthetic staging promotion changed only staging; production without evidence denied |
| Markdown, local file links, Mermaid | Passed: 64 Markdown files and 12 diagrams; original LICENSE verified |
| Local Trivy dependency scan | Not verified: vulnerability DB download was forcibly interrupted by upstream connection closure; no successful scan claimed |
| Local Docker builds/kind admission | Not executed: Windows Docker engine unavailable; Linux CI is the validation path |

Native Kubernetes 1.35 strict schemas and Argo CD v3.5.7 schemas are vendored with provenance so rendering/validation works offline. Exact tool downloads have repository-pinned SHA-256 checksums. Upstream license notices are retained separately; project LICENSE is unchanged.

## CI evidence and acceptance boundaries

The new `Secure delivery checks` workflow gates dependency/secret/IaC findings and builds/scans five application images with SBOM artifacts. Existing Linux workflows exercise containers, migrations, kind, dashboard and recovery. The kind workflow also exercises real native admission acceptance/denials. Record actual run results here after execution; configured jobs are not proof of passing acceptance.

Cloud release/promotion paths are deliberately not dispatched. Administrator environment protections, independent reviewers, OIDC IAM, ECR repositories, GitHub App, real stores/OIDC/secrets/network egress, controller installation, live signature/attestation verification and actual Argo reconciliation remain operator prerequisites. No live AWS/GitOps acceptance is claimed. Receipts capture deployment readiness and need independent application/SLO review. There is no admission-time signature controller or byte-identical-build certification.
