# ADR 0003: Local-first delivery and cloud approval

Status: Accepted design | Date: 2026-11-02

## Decision

Phase 00 ships documentation and validation only. Phase 01 uses native development and Linux Docker Compose for a dashboard/API health slice. Introduce an isolated kind lab in a later phase after a local-cluster ADR; k3d is an alternative. Use synthetic fixtures before cluster data. No AWS call or infrastructure provisioning is part of this foundation.

Future EKS staging requires separate authorization, Terraform state/identity/network design, regional cost estimate, budgets, review, and teardown proof. Production requires tested recovery, RPO/RTO, SLOs, ownership, security review, and image/promotion/rollback controls. GitHub Actions builds/verifies; Argo CD reconciles approved deployment state. Application remediation must not fight GitOps ownership.

## Alternatives and consequences

Starting on EKS can match the eventual environment but introduces cost, identity/network complexity, and destructive-action risk too early. Local-first delivery reduces cost and supports reproducible tests; local results do not prove cloud availability, performance, IAM safety, or production readiness.
