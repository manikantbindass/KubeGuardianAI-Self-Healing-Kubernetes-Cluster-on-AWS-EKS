# AWS cost considerations

Phase 00 creates **no AWS resources** and makes no AWS API calls. This is a planning checklist, not a quote or authorization to provision. The eventual region, account, uptime, cluster size, telemetry volume, retention, and availability requirements are unknown; a numeric estimate would be unsupported.

## Cost drivers

| Driver | Estimate inputs / controls |
| --- | --- |
| EKS control plane and Kubernetes support tier | Region, cluster-hours, selected Kubernetes version and support lifecycle; avoid abandoned clusters |
| Worker compute and EBS | Instance families/count, architecture, utilization, runtime, disk size/IOPS/snapshots, autoscaling bounds |
| Network | NAT gateways/hours/processed data, interface endpoints, load balancers, public IPv4, inter-AZ and internet egress; compare topology costs |
| PostgreSQL / Redis | Managed versus self-hosted, size, replicas/Multi-AZ, backup retention, storage, I/O, data transfer; do not assume serverless is free |
| Observability | Metric/cardinality, log ingestion/query volume, retention, managed-service fees, object archive/lifecycle; avoid duplicate collectors |
| Object storage / backups / audit | Retained bytes, requests, retrieval, replication, immutable retention period and deletion constraints |
| Security / delivery | KMS requests/keys, secret storage/rotation, registry storage/scans, CI runners, image transfer |
| Optional AI | Provider/model, tokens/requests, retrieval compute/storage, regional/privacy requirements and hard usage limits |

## Estimation method and approval gate

Use the [AWS Pricing Calculator](https://calculator.aws/) with actual region and workload inputs; verify current [EKS pricing](https://aws.amazon.com/eks/pricing/) and service-specific rates immediately before review. Do not assume credits or free tiers. Record pricing date, currency, taxes/support assumptions, low/expected/high utilization, and a monthly ceiling.

Model monthly cost as control-plane hours + compute hours + storage/IO + network/egress + observability + persistence + security/delivery + optional AI. Include idle costs and teardown delay. Costs depend on architecture; the table is a checklist, not an exhaustive bill.

Before any apply, obtain separate explicit authorization and review the saved Terraform plan, state backend access, IAM, network, budget estimate, resource tags, retention, and cleanup. Enable budget/cost-anomaly notifications and assign an owner. Budget alerts are not a guaranteed hard stop. Keep lab TTL/teardown automation and bounded autoscaling; do not reuse production credentials.

## Teardown and evidence

Prefer local kind/Compose until cloud-specific behavior is required. Future teardown must enumerate clusters, nodes, load balancers, EBS/snapshots, NAT/endpoints, IPs, registry artifacts, databases/caches, logs, archives, and state resources. Verify residual resources in the correct account/region after teardown. Immutable audit retention and backups may intentionally persist and incur cost; record exceptions and owners. Never use an unscoped account-wide delete script.
