# Infrastructure

Phase 02 provides local kind configuration, Helm charts, namespace manifest and tested lifecycle scripts. Phase 03 adds modular [Terraform EKS infrastructure code](terraform/README.md) with dev/demo environments and separate state bootstrap. Argo CD, cloud application deployment and production monitoring remain future integrations. No AWS resources have been provisioned.

Start with an isolated local lab before cloud deployment. EKS requires separate explicit authorization, IAM/network/state design, current regional cost review, budgets, ownership and teardown proof. See [cost considerations](../docs/costs/aws-cost-considerations.md) and [roadmap](../docs/roadmap.md).
