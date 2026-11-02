# Contributing

Phase 00 architecture and Phase 01 local runtime are included. Keep implemented behavior separate from proposed functionality in every document and PR.

## Workflow

1. Branch from current `main`: `feat/<issue-or-scope>`, `fix/<scope>`, `docs/<scope>`, `chore/<scope>`, or `ci/<scope>`. This foundation uses `feat/phase-01-foundation`.
2. Keep commits focused. Use `<type>(<optional-scope>): <imperative summary>`, for example `docs(architecture): define execution boundary`. Prefer subjects under 50 characters; add rationale for breaking or security changes. Never rewrite shared history.
3. Run the [development checks](docs/development-guide.md). Record exact outcomes and blockers in the PR.
4. Add an ADR when trust boundaries, storage, service interfaces, deployment, or technology choices change. Use the [ADR template](docs/architecture/adr-template.md).
5. Open a PR against `main`; obtain review and required checks before merge. Squash merge is recommended once an administrator enables it. Do not force-push `main`; preserve the initial commit and license.

## Standards

Use UTF-8, LF endings, final newlines, two spaces in configuration/TypeScript, and four spaces in Python. Use relative Markdown links, descriptive headings, fenced code with language identifiers, and editable Mermaid source. Update roadmap gates when scope changes.

TypeScript uses strict types, ESLint, explicit dependency versions and npm locks. Python uses Ruff, strict mypy, behavioral tests, explicit pins and a uv lock. Change pins and locks together, then run clean frozen installs and all relevant checks. Architecture alternatives require documented tradeoffs, not extra services by default.

Do not commit credentials, kubeconfigs, Terraform state, production telemetry, personal data, caches, or large model binaries. Contributions remain under Apache 2.0. Preserve LICENSE bytes and existing files.

## Operational boundaries

No cluster or cloud action is authorized by a documentation PR. AWS provisioning requires a separately approved phase, reviewed estimate, least-privilege design, and teardown evidence. Recovery requires opt-in, dry-run, default-deny policy, approval, bounded actions, idempotency, cooldowns, audit, verification, and rollback. Assistant output cannot authorize actions.

Administrators should enable branch protection, required checks, PR reviews, private vulnerability reporting, and dependency alerts after the first CI run. These are recommendations; Phase 00 does not change repository settings.
