# Secure delivery and GitOps

Phase 08 supplies CI and controlled release automation. **No AWS resources, ECR releases or live Argo CD installations were created during implementation.** Release and promotion workflows require manual dispatch on `main`; delivery is disabled until repository administrators configure `DELIVERY_ENABLED=true` and protected environments. A passing scan is a dated observation, not a vulnerability-free guarantee.

## Quality and supply-chain checks

Existing workflows retain backend Ruff/mypy/pytest, frontend lint/types/component tests/build, PostgreSQL migration round-trip, Compose startup, kind, telemetry, ML reproducibility and operator/browser integration. They now run on pull requests and `main` pushes. All `uses:` references are immutable reviewed SHAs listed in `.github/security/actions.lock.json`; Dependabot proposes updates.

`security.yml` adds actionlint, full-history redacted Gitleaks, Trivy dependency/secret scanning, locked Checkov Terraform scanning, offline Argo CD schemas, Helm rendering and Kubernetes validation. Five application images (API, dashboard, operator, detector, isolated demo workload) are independently built/scanned with blocking HIGH/CRITICAL findings, including unfixed vulnerabilities. CycloneDX SBOMs and raw reports are retained as workflow artifacts. PR jobs have read-only tokens and no AWS credentials or publishing rights. The former advisory application-image scan was replaced by these blocking jobs.

The five Dockerfiles pin their existing base images by digest, retain non-root users, and use frozen package locks. BuildKit receives the source commit timestamp and OCI source/revision labels. This improves repeatability; byte-identical rebuilds and SLSA certification are **not** claimed. Vulnerability databases change and are intentionally refreshed. Third-party monitoring images, external stores and infrastructure controllers need their own release/advisory review before production use.

Native admission tests in disposable kind verify that approved ECR digests are accepted and tags, foreign registry prefixes and mutable init containers are denied. Namespace Pod Security `restricted` enforcement, the application's read-only filesystems/capability drops/probes, NetworkPolicy and scoped operator/bridge RBAC remain necessary. Digest admission does not cryptographically verify a signature: promotion verifies signatures before Git changes. Install and test a separate Sigstore policy-controller/Kyverno verification policy before claiming admission-time signature enforcement.

## Local validation: Windows and Linux/macOS

Use Python 3.12, uv 0.13.6, Helm 3.19.0 and the project toolchain. The locked downloadable tools support **Windows/Linux x86_64**. On macOS install and verify matching upstream tools separately, then put them on PATH; the Python installer deliberately rejects unsupported architectures/platforms rather than choosing an unverified binary.

```powershell
# Windows PowerShell, from repository root
uv sync --frozen
uv sync --project .github/security --frozen
uv run python scripts/security_tools.py actionlint gitleaks trivy kubeconform
.tools/delivery/actionlint/actionlint.exe
.tools/delivery/gitleaks/gitleaks.exe git --redact .
uv run --project .github/security python scripts/validate_delivery.py
uv run pytest tests/unit/test_delivery.py -q
# Checkov's Windows .cmd launcher can choose the wrong Python; invoke its pinned environment:
.github/security/.venv/Scripts/python -c "from checkov.main import Checkov; Checkov().run()" -d infrastructure/terraform --framework terraform --skip-download --output json > .cache/delivery/checkov.json
uv run python scripts/security_gate.py checkov .cache/delivery/checkov.json
```

```bash
# Linux; macOS uses separately verified native tools on PATH
uv sync --frozen
uv sync --project .github/security --frozen
uv run python scripts/security_tools.py actionlint gitleaks trivy kubeconform
export PATH="$PWD/.tools/delivery/actionlint:$PWD/.tools/delivery/gitleaks:$PWD/.tools/delivery/trivy:$PWD/.tools/delivery/kubeconform:$PATH"
actionlint
gitleaks git --redact .
uv run --project .github/security python scripts/validate_delivery.py
uv run pytest tests/unit/test_delivery.py -q
# Findings return 1; retain the report and run the gate. Other exit codes are tool failures.
uv run --project .github/security checkov -d infrastructure/terraform --framework terraform --skip-download --output json > .cache/delivery/checkov.json
uv run python scripts/security_gate.py checkov .cache/delivery/checkov.json
```

The validator uses explicit synthetic digests in a temporary copy, renders staging and production, validates 22 resources, prepares staging changes and asserts production is untouched. This is an offline promotion contract test, not a deployed staging acceptance test. Windows Docker engine availability is required for image/cluster checks; Linux CI performs them when local Docker is unavailable. Use `python scripts/image_delivery.py build --component api --source <full-HEAD-SHA>` with Docker, Buildx and Trivy on PATH for an actual gated image build.

## One-time administrator setup

1. Merge the stacked foundations through normal review. Protect `main`: require reviews/CODEOWNERS, restrict force pushes/deletions, and require all quality/security checks. Treat changes to workflows, exceptions, GitOps and release scripts as sensitive. The default CODEOWNER is the repository owner; configure at least one **independent** release reviewer. A sole maintainer cannot self-approve a protected delivery job.
2. Create GitHub environments named `staging` and `production`. Configure required independent reviewers, prevent self-review, disable administrator bypass, and allow exactly the custom **branch** policy `main` (no wildcard/tags). The preflight queries these settings and fails closed if absent or unreadable; verify the repository's plan supports these protections. Never rely on an automatically created unprotected environment.
3. After explicit cost approval, an authorized Terraform operator may enable `enable_delivery_roles` using an existing GitHub OIDC provider. Review the plan; no workflow here runs Terraform apply/destroy. The new module creates `staging-publish`, `staging-verify` and `production-verify` roles with ECR-only permissions. Only the publisher can upload. No EKS access or infrastructure mutation permission is granted. The older branch-bound Phase 03 publisher remains a separate legacy option and is not used by these workflows.
4. Configure environment variables `AWS_REGION`, `AWS_ACCOUNT_ID`, `ECR_REGISTRY` (account registry), `ECR_PREFIX` (registry/project), `AWS_VERIFY_ROLE_ARN`, and staging-only `AWS_PUBLISH_ROLE_ARN`. Never configure long-lived AWS keys. ECR repositories must already exist; Terraform adds repositories for all five images, with immutable tags and encryption. Review lifecycle retention for signed digests and OCI signature/SBOM referrers; retain deployed/rollback releases before cleanup.
5. Create a GitHub App installed **only on this repository**, with Contents write and Pull requests write. Configure `PROMOTION_APP_ID` and encrypted environment secret `PROMOTION_APP_PRIVATE_KEY`. The action mints a short-lived, narrowly scoped installation token for the promotion PR and revokes it on completion. This is a GitHub integration credential, never an AWS key. A PR made with `GITHUB_TOKEN` would suppress ordinary downstream checks.
6. Set repository variable `DELIVERY_ENABLED=true` only after review. Publication uses protected `staging`; production Git promotion uses separately protected `production`. AWS OIDC environment subjects do **not** contain the branch: repository/environment restrictions live in IAM, while the main-only restriction is enforced by GitHub environment branch policy and workflow/preflight checks. Review [GitHub OIDC claims](https://docs.github.com/en/actions/reference/security/oidc) and [AWS environment guidance](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-idp_oidc.html).

## Release and staging promotion

1. Wait for all 22 required source checks on the exact `main` commit. Dispatch **Approved ECR release** on `main` with `vMAJOR.MINOR.PATCH` or `-rc.N`. Review and approve the staging job. These actions write billable ECR storage and public Sigstore transparency records; confirm account, costs and source metadata disclosure before approval.
2. The job builds/scans all five images, pushes immutable run-specific tags, resolves digests, re-scans the registry digests, keylessly signs them and attaches CycloneDX and source/run-bound provenance attestations. It uploads `verified-release` and creates a **draft** GitHub release. Failures may leave partial ECR uploads but cannot produce a complete promotion artifact; remove them only after inspecting the run. The workflow does not create a cluster or sync Argo CD.
3. Dispatch **Reviewed GitOps promotion**, supplying the successful release run ID and `staging`. It checks the trusted workflow/main/source/checks, verifies Sigstore issuer/identity and digest-bound attestations, then opens a PR changing three staging files only. Merge requires normal review and checks; no auto-merge is configured. Configure repository protections to prevent direct writes by people/apps outside the reviewed flow.
4. An authorized staging operator reviews the Argo diff and manually syncs. Application manifests initially point at the deliberately nonexistent `release-not-configured`; they cannot deploy until promotion selects an immutable chart commit. Configure real OIDC URLs, secret objects, stores, network access and external dependencies first. The examples' `.invalid` hostnames are intentional blockers, not working endpoints.
5. After rollout and application/SLO smoke tests, collect read-only deployment evidence with `python scripts/delivery.py verify-staging --release infrastructure/argocd/environments/staging/release.json --context <explicit-approved-context> --output infrastructure/argocd/environments/staging/verification.json`. The script verifies exact image digests, observed generations and all replicas ready/available/updated (minimum two) for API/dashboard/worker. Review and commit the receipt through a PR with operational evidence attached. Receipts are operator attestations, not cryptographic proof of all application behavior; deployment readiness alone does not establish SLO compliance.
6. Production promotion requires the identical staged release and a matching receipt no older than 24 hours. Dispatch promotion with `production`, obtain independent approval, review/merge its PR, inspect the Argo diff, then explicitly authorize production sync. The workflow's production role can only read ECR. Operator and detector images are published for separate reviewed installations; this application promotion deploys API, dashboard and the API worker only.

## Ownership, drift and rollback

Terraform owns VPC/EKS/nodes/IAM/KMS/ECR/log groups and optional Pod Identity associations. Platform administrators own Argo CD/controllers/CRDs, restricted namespaces, namespace registry annotations, secret integration and GitHub environment protections. Argo applications own only their namespace-scoped application allowlist: no Namespaces, Secrets, RBAC roles, CRDs or cluster resources. Do not import the same application resources into Terraform/Helm CLI ownership. The service account is application-owned; external-secrets' service account is platform-owned.

Argo compares the immutable chart revision plus reviewed environment files on `main` and displays drift/health. Auto-sync, pruning and self-heal are intentionally disabled; no ignore-differences hides mutations. Configure Argo notifications/alerting separately; it is not installed by this phase. Projects allow one namespace each. Restrict cluster credentials and controller access to the intended environment as well; an AppProject is not a replacement for Kubernetes RBAC.

For rollback, revert the environment's `application.json`, `images.json` and `release.json` to a prior signed release through a reviewed PR; verify signatures/retention, inspect the diff and manually sync. Argo history is a diagnostic aid; restore Git as source of truth after emergency rollback. Migration jobs run at Sync wave 1 after config/services, before deployments at wave 2, and are deleted only on success. A failed migration blocks subsequent rollout. Prefer backward-compatible expand/contract migrations and image rollback; never automatically downgrade a database or destroy audit data. Stop and restore from an independently tested backup if schema incompatibility makes rollback unsafe.

## Secrets, scans and failures

See [secret integration](../../infrastructure/kubernetes/security/README.md) for optional namespace-scoped External Secrets/EKS Pod Identity. Git stores references only. Application restarts are needed when environment-based secrets rotate; test rotation and rollback. Configure explicit egress for OIDC/JWKS, PostgreSQL/Redis and telemetry before sync; the default network policy permits same-app traffic and DNS only. There is no broad default Internet egress. Choose approved CIDRs or namespace/pod selectors for the actual installation.

`exceptions.json` accepts exact scanner/id/scope entries with owner, tracking issue, reason and expiry (maximum 90 days). Unknown fields, wildcard scope, expired entries and parser failures fail closed; secret findings cannot be waived there. [Issue #10](https://github.com/manikantbindass/KubeSentinel-AI/issues/10) tracks seven proposed Terraform exceptions expiring 2026-12-03. Review these before enabling delivery. No CVE waiver is seeded. The only Gitleaks exclusion is the exact historical fingerprint of a non-secret idempotency test string. Never suppress an entire directory/rule or rewrite repository history to hide a finding.

If a scanner database download fails, retry with working network access; do not call the scan passed. If environment preflight returns 403, obtain appropriate read visibility or administrator verification of the API capability; do not remove the gate. OIDC `AccessDenied` requires checking exact subject/audience, environment branch restrictions, approved account and ECR resource ARNs. A missing/expired artifact, failed signature or mismatched source/run must stop promotion. Rebuild a reviewed release instead of editing evidence or substituting a tag.
