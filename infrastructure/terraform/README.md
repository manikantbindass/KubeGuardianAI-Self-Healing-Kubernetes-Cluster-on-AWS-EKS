# AWS infrastructure as code — Phase 03

**No live AWS deployment is claimed. No apply/destroy is authorized by these files.** This code defines a deployable EKS infrastructure baseline for an authorized operator after cost, identity, compatibility and plan review. Application production readiness is a separate gate: Phase 02 image scans contain HIGH/CRITICAL findings and the API remains unauthenticated.

## Layout and toolchain

| Path | Responsibility |
| --- | --- |
| `bootstrap/` | Separately approved S3/KMS remote-state resources, local state initially |
| `environments/dev/` | Single-NAT, one-node cost-focused starting profile |
| `environments/demo/` | Two-AZ NAT and two-node production-like demonstration profile |
| `modules/network/` | VPC, public/private subnets, routes, NAT choices, endpoints, flow logs |
| `modules/eks/` | EKS API, managed AL2023 nodes, add-ons, launch template and scoped access entries |
| `modules/iam/` | Control plane, nodes, CNI Pod Identity, optional GitHub ECR publisher |
| `modules/ecr/` | Immutable-tag API/dashboard repositories, KMS encryption, scanning, retention |
| `modules/observability/` | KMS CloudWatch groups, flow-log writer, audit 403 metric/alarm |
| `modules/workload_identity/` | Optional log-writer Pod Identity; no application permissions by default |
| `modules/dns/` | Optional CNAME in an existing zone for an existing internal LB |
| `modules/platform/` | Composition, KMS key and guarded configuration |

Terraform 1.13.5 (constraint `>=1.13.5,<1.14.0`) and AWS provider **6.71.0** are selected explicitly. Commit provider locks for each root; initialization and checks do not require credentials when `-backend=false` is used. Local module paths avoid mutable remote module dependencies. Add-on versions and node AMI release are required explicit inputs, not moving `most_recent` data sources. Example sentinel versions must be replaced with regional compatibility evidence before planning.

## Safe checks (no AWS resources)

```sh
terraform fmt -check -recursive infrastructure/terraform
terraform -chdir=infrastructure/terraform/environments/dev init -backend=false -input=false
terraform -chdir=infrastructure/terraform/environments/dev validate
# Repeat for environments/demo and bootstrap.
trivy config --severity HIGH,CRITICAL infrastructure/terraform
helm lint infrastructure/helm/kubesentinel -f infrastructure/helm/kubesentinel/values-prod.yaml
helm template sentinel infrastructure/helm/kubesentinel -f infrastructure/helm/kubesentinel/values-prod.yaml
```

Commands are the same in PowerShell, bash and zsh. On Windows place the Terraform/Trivy binaries on PATH or use their absolute paths. Do not append credentials to command lines. `init -backend=false` downloads providers; it does not configure AWS, fetch state or provision infrastructure. A static scan is not an IAM simulation, a live plan, or a security certification. See [validation](../../docs/reports/phase-03-validation.md) for exact results and limits.

Read [module reference](../../docs/architecture/terraform-reference.md), [operator runbook](../../docs/runbooks/aws-eks.md), [state bootstrap](../../docs/runbooks/terraform-state.md), [cost assumptions](../../docs/costs/eks-estimate.md), and [local/cloud matrix](../../docs/architecture/local-vs-cloud.md) before planning. No CI job contains an apply/destroy command or AWS credential configuration.
