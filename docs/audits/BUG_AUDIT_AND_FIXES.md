# Bug audit and verified fixes

Date: 2026-11-04. Branch: `codex/release-audit`. Integration PR:
[PR #15](https://github.com/manikantbindass/KubeSentinel-AI/pull/15).
Historical unresolved statuses below refer to their original scans. The security follow-up at the end records the verified remediation and supersedes AUD-005/AUD-006 blocking statuses.

## AUD-001: insecure API signing-key transport

- Severity: **High**. Root cause: the API checked that OIDC issuer/JWKS settings
  were present but accepted HTTP URLs. A misconfigured HTTP key endpoint permits
  key substitution in transit and can undermine token authentication.
- Affected: `apps/api/kubesentinel_api/operations/auth.py` and the OIDC runbook.
- Fix: require HTTPS issuer and JWKS URLs before attempting key retrieval.
  Local development tokens remain an explicit separate mode.
- Regression: `test_oidc_rejects_insecure_key_transport_before_fetch`, parameterized
  for both endpoints, asserts HTTP 503 and that key lookup never runs.
- Verification: focused operations tests and complete Python suite pass.
- Status: **RESOLVED** for the reproduced HTTP configuration defect. A real OIDC
  tenant remains a separate integration prerequisite.

## AUD-002: artifact gate omitted from release acceptance

- Severity: **Medium**. Root cause: Phase 11 added a portfolio workflow job but
  the explicit release source-check allowlist still described Phase 10.
- Affected: `scripts/delivery.py`, `tests/unit/test_delivery.py`.
- Fix: require successful `portfolio` on the exact release source commit.
- Regression: missing and failed portfolio checks both reject publication;
  a complete successful check set is accepted by the mocked preflight.
- Verification: delivery regressions and full Python suite pass.
- Status: **RESOLVED**. No publication workflow was dispatched to test it.

## AUD-003: intelligence absent from the local preview API

- Severity: **Medium**. Root cause: the explicit synthetic SQLite preview included
  only the Phase 07 operations router, omitting later intelligence routes.
- Affected: `scripts/operations_preview.py`, new preview regression test.
- Fix: include the same authenticated intelligence router used by the real API.
- Regression: unauthorized requests receive 401, synthetic analysis returns
  explanations, and real mode stays empty rather than using demo records.
- Verification: preview regression and full Python suite pass.
- Status: **RESOLVED**. This does not convert preview storage into PostgreSQL/Redis.

## AUD-004: vulnerable operator dependencies and compiler

- Severity: **High**. Root cause: pinned Go networking/text modules and compiler
  predate the fixes reported by the repository's actual Trivy scan.
- Affected: `operator/go.mod`, `operator/go.sum`, operator Dockerfile,
  operator/operations workflow compiler mappings and local recovery launchers.
- Fix: `golang.org/x/net` v0.60.0 with its required `x/text` v0.42.0 and compatible
  indirect modules; Go 1.26.10 throughout. Regenerate the dependency lock normally.
- Verification: `go mod verify`, `go test ./... -count=1`, `go vet ./...` pass;
  fresh Linux operator image security, Windows/Linux Go and isolated recovery
  jobs pass on `5ef44f5`. Operator image now has zero HIGH/CRITICAL findings in
  the downloaded Trivy report. The dependency scan no longer reports these modules.
- Status: **RESOLVED** for reported operator vulnerabilities. Other image failures
  remain separate findings; no global clean-supply-chain claim is made.

## AUD-005: stale runtime packages and unnecessary runtime npm

- Severity: **Critical** (maximum dashboard image advisory severity). Root cause: old digest-pinned runtime snapshots retain
  patched OS vulnerabilities, and the standalone dashboard ships npm although
  it runs directly with Node.
- Affected: API/detector/demo/dashboard Dockerfiles, base-image lock, `.nvmrc`
  and development toolchain documentation.
- Fix: registry-verified Python 3.12.16 and Node 24.22.2 images with immutable
  digests; remove runtime npm/npx. No unpinned package upgrade or CVE suppression.
- Verification: fresh Compose, detector, browser, telemetry and kind jobs pass;
  image rescans show all remaining HIGH/CRITICAL entries have no supplied fixed
  version. The operator image passes. API/detector/demo retain 45 findings each;
  dashboard retains 33, including CVE-2023-45853 in Debian 12 zlib. Counts are advisory entries, not unique exploit paths. The supported digest-pinned Debian 13 Node runtime was then built and scanned on `6822b84`: critical findings are zero, while 44 unfixed HIGH advisories remain. The runtime change is verified; the overall image gate is still failing.
- Status: **PARTIALLY RESOLVED / RELEASE BLOCKING**. Available fixed-version
  findings were removed; unfixed advisories require a supported clean runtime or
  explicit reviewed treatment. This audit adds no vulnerability exception.

## AUD-006: Checkov tooling dependency has an unfixed advisory

- Severity: **High** (scanner rating). Root cause: locked Checkov 3.4.3 directly
  requires `ecdsa` 0.19.2, flagged as CVE-2024-23342 without a fixed version.
- Affected: `.github/security/pyproject.toml`, `.github/security/uv.lock` and
  the static security workflow's dependency gate.
- Verification: downloaded Trivy report for `5ef44f5` has only this remaining
  HIGH/CRITICAL source dependency finding. The gate correctly fails.
- Status: **UNRESOLVED / RELEASE BLOCKING**. Do not remove the dependency from a
  generated lock, skip the scanner, or declare it harmless solely because it is
  tooling. Obtain an upstream replacement/fix or separately reviewed treatment
  while retaining meaningful Terraform security checks.

## AUD-007: dashboard correlation bypasses scoped backend evidence

- Severity: **Medium**. Root cause: AI Insights linked any incidents sharing a
  workload name, ignoring namespace/time; the browser proxy omitted the Phase 10
  intelligence read endpoint. The graph could show misleading relationships.
- Affected: dashboard proxy, typed operations client, Insights view and section
  wiring; new proxy tests and extended component tests.
- Fix: query typed intelligence with mode and selected namespace, use only API
  `related_ids` for edges, display ranked hypotheses, evidence IDs and retrieved
  runbook steps, and show loading/empty/error states with retry. No mutation path
  or provider privilege is added to intelligence.
- Regression: same-name workloads in different namespaces produce zero edges
  without API evidence; API outage shows no inferred correlations. Proxy forwards
  the authenticated scoped read but still rejects internal ingestion and
  intelligence POSTs.
- Verification: frontend type-check and all 20 component/proxy tests pass.
  Clean installation, lint, build and fresh Linux frontend/browser checks pass
  on `38e3e5a`; all 20 component/proxy tests pass.
- Status: **RESOLVED**, including fresh frontend/browser CI acceptance.

## AUD-008: moderate lint-tool glob denial-of-service advisory

- Severity: **Medium**. Root cause: the ESLint ecosystem still resolves
  `minimatch` versions covered by GHSA-g3hv-75wg-m249. A clean `npm ci` followed
  by full `npm audit` reports 16 moderate affected packages through this graph.
- Affected: development tooling in `package-lock.json`; `npm audit --omit=dev`
  reports zero runtime advisories.
- Status: **UNRESOLVED tooling risk**. npm proposes incompatible major downgrades
  of ESLint/Next configuration; the fixed minimatch major also changes consumers'
  API contract. No unsafe force-fix or untested override was applied. Upgrade
  compatible lint consumers when available and rerun lint/types/tests/build.

## Data/model review outcomes

No reproducible feature leakage, serialization mismatch or inconsistent scoring
preprocessing was found in the executed tests. Tests compare saved/reloaded
models, mutate held-out features without changing learned preprocessing/model/
thresholds, and reproduce held-out predictions. Independent synthetic generate,
train and evaluate commands produce byte-identical repeated `predictions.csv`.
Rule fallback and model/data-quality/version checks remain tested. Thresholds
are selected on validation data, not test labels; confidence stays explicitly
uncalibrated. This is bounded synthetic evidence, not proof of useful production
thresholds or real false-positive rates.

## Review coverage and limits

Repository-wide compile, lint/type, unit, frontend build, schema, IaC/security,
link and artifact checks complement targeted review of authorization, command
transactions, recovery mutation boundaries, telemetry, model training/inference,
workflows and GitOps. A passing scanner does not establish absence of every bug.
See the [phase audit](PHASE_COMPLETION_AUDIT.md) and
[final gates](FINAL_RELEASE_READINESS.md) for incomplete capabilities and blockers.

## Security remediation follow-up

Candidate changes replace the four Debian application image runtimes with official digest-pinned Alpine 3.24 equivalents. They must pass musl dependency installation, application startup, browser/cluster tests and Trivy gates before any clean-scan claim. No suppressions are added.

Checkov is now an explicit downstream `3.4.3+sentinel.1` build: the two public-key verification modules use OpenSSL-backed cryptography, and python-ecdsa is removed entirely. The checksum-verified wheel builder, retained upstream license, regenerated wheel RECORD and signature boundary regressions are in [.github/security/checkov-patch](../../.github/security/checkov-patch). Four regression groups pass locally; real scanner and fresh CI validation remain required. This is not claimed as an upstream fix.

## Verified resolution of AUD-005 and AUD-006

Both blocking findings are **RESOLVED** on `f882be6`. All five final image reports have zero HIGH/CRITICAL findings and zero detected secrets; the dependency scan and patched Checkov Terraform/crypto checks pass. See [machine-readable evidence](../reports/release-audit/security-remediation.json). The package replacement removes the vulnerable module and preserves signature verification rather than excluding findings. The runtime changes remove vulnerable Debian packages rather than editing scanner databases. MEDIUM/LOW/UNKNOWN findings remain recorded. AUD-008 moderate lint-tool risk remains separate from the HIGH/CRITICAL gate.
