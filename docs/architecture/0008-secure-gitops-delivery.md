# ADR 0008: reviewed digest-based delivery

Status: accepted for implementation; live cloud delivery remains operator-gated.

Application quality checks and artifact security checks run with read-only PR tokens. A manual workflow on protected `main` verifies the exact source's required checks, enters a protected staging environment, assumes an ECR-only AWS role using OIDC, rebuilds/scans images, and produces digest references, SBOMs and keyless signatures/provenance. No infrastructure apply, cluster credentials or Argo sync permission is granted to the publisher.

Promotion independently verifies release origin, source checks, signatures and attestations, then opens a GitOps PR using a scoped ephemeral GitHub App token. Each application uses an immutable chart revision and reviewed environment files. Auto-sync/prune/self-heal are disabled; Argo still compares live state and reports drift. Production requires separate approval and the identical staged release with recent operator-reviewed evidence.

Terraform owns infrastructure and optional workload identity. Argo owns an explicit namespace application allowlist. Cluster-wide controllers, namespaces, RBAC and secrets are platform responsibilities. This avoids Terraform/Argo fighting over the same resources. Environment-bound IAM subjects replace branch subjects for protected jobs; branch restriction is enforced by GitHub's main-only environment policy because standard environment subjects omit the branch.

Alternatives: direct kubectl from Actions grants CI cluster access and weakens drift visibility; tag-based deployment permits mutable artifacts; automatic production sync reduces approval opportunities. Flux is a reasonable GitOps alternative. GHCR is a lower-setup registry alternative; ECR is selected for existing EKS/IAM integration. Sigstore improves verifiable artifact identity, but this implementation is not a hermetic builder or SLSA certification. Independent admission-time signature verification remains an optional controller integration.

Consequences: initial applications deliberately cannot resolve `release-not-configured`; an authorized first release, real secrets/stores/OIDC/network configuration and administrator environment setup are prerequisites. A sole maintainer cannot satisfy independent approval. Artifact expiry, OCI-referrer retention and schema migration compatibility must be managed. See the [delivery runbook](../runbooks/secure-delivery.md) and [editable diagram](../diagrams/secure-delivery.mmd).
