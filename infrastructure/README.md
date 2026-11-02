# Infrastructure (future)

Planned boundaries: Terraform modules/environments, local Kubernetes manifests, Helm packaging, Argo CD applications and monitoring. No resources or deployable cluster definitions are introduced here. Phase 01 uses root Docker Compose only.

Start with an isolated local lab before cloud deployment. EKS requires separate explicit authorization, IAM/network/state design, current regional cost review, budgets, ownership and teardown proof. See [cost considerations](../docs/costs/aws-cost-considerations.md) and [roadmap](../docs/roadmap.md).
