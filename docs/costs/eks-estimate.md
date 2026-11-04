# EKS inventory and cost-estimate assumptions

No resources exist as a result of Phase 03. No AWS bill, account-specific quote or live pricing API result is available. Values below are **illustrative budget assumptions**, not current ap-south-1 prices. Before cost approval, replace every assumed unit price with a dated [AWS Pricing Calculator](https://calculator.aws/) estimate for the exact account, region, support tier and workload. Refer to [EKS pricing](https://aws.amazon.com/eks/pricing/) and [VPC pricing](https://aws.amazon.com/vpc/pricing/) for current charge categories. Do not infer free-tier eligibility or credits.

## Resource inventory

| Resource | Dev default | Production-like demo default |
| --- | --- | --- |
| VPC / AZ layout | One VPC, two public + two private subnets, IGW, private/public routing | Same topology, separate CIDR/account/state recommended |
| NAT gateways / EIPs | One, cross-AZ traffic possible | Two, one per private subnet AZ |
| Private endpoints | Optional seven interface services × two AZs + S3 gateway | Same; optional alongside NAT or mandatory without NAT |
| EKS | One, private API, all five control-plane log types | Same, standard support only |
| Managed nodes / disks | One desired t3.large, min one/max three, 30GiB gp3 encrypted each | Two desired/min two/max three, 30GiB each |
| KMS | One rotating environment key/alias | One separate environment key/alias |
| ECR | Five repositories (API, dashboard, operator, detector, demo workload), immutable tags, scan-on-push, bounded image retention | Same |
| CloudWatch | Three groups; flow log writer; audit filter + one alarm; 14-day retention | 30-day retention |
| IAM / access | Cluster/node/CNI roles; optional scoped access entries; no app role by default | Same |
| Optional integrations | Existing-provider GitHub ECR publisher, Pod Identity log writer, existing-zone CNAME | Same; all disabled by default |
| State bootstrap | Separate S3 bucket/versioning/encryption/access controls and separate KMS key | Independent lifecycle; not an ephemeral-cluster resource |

No RDS/ElastiCache, load balancer, hosted zone, certificate, VPN, bastion, metrics-server, cluster autoscaler, collector, GitOps controller or product identity provider is provisioned. Those add costs if separately approved. Terraform-controlled max nodes does not bound costs from resources created outside Terraform or external controllers.

## Worked planning example (assumed prices, USD)

Assume 730 hours/month, standard EKS support at **$0.10/cluster-hour**, t3.large at **$0.10/node-hour**, NAT at **$0.05/gateway-hour** plus **$0.05/GB**, gp3 at **$0.10/GiB-month**, 20GB NAT processing, and a **$25/month allowance** for logs/ECR/state/KMS/requests. These rounded prices are scenario inputs, not a quote or promised ceiling.

| Scenario | Illustrative subtotal calculation | Illustrative monthly subtotal |
| --- | --- | --- |
| Dev, 1 node, 1 NAT, no interface endpoints | 73 EKS + 73 node + 36.50 NAT + 1 processing + 3 EBS + 25 allowance | $211.50 |
| Demo, 2 nodes, 2 NAT, no interface endpoints | 73 EKS + 146 nodes + 73 NAT + 1 processing + 6 EBS + 25 allowance | $324.00 |
| Add seven interface endpoints in two AZs, assumed $0.01/AZ-hour/service | 7 × 2 × 730 × 0.01, plus endpoint processing | +$102.20 before processing |

These subtotals exclude tax/support, public IPv4/NAT EIP charges, inter-AZ/data-out, burst CPU credits, backups, externally provisioned database/cache, load balancers, DNS, TLS/certificate charges if applicable, additional scan/observability products and unusual storage/query volume. They **underestimate a complete application environment**. At max three nodes add two extra node-hours per dev hour (one extra for demo), plus disks/transfer. Use a high-utilization case and contingency in the approved budget. A 48-hour lab reduces hourly items but not necessarily all retention/storage charges; leaving EKS running with zero nodes still incurs control-plane charges.

## Tradeoffs and controls

- Single NAT saves fixed hourly cost but creates an AZ dependency and potential cross-AZ charges. Per-AZ NAT improves zonal independence at greater baseline cost. No NAT plus endpoints can cost more at low volume and excludes general internet egress; calculate both options.
- On-demand gives simpler demonstrations; Spot can interrupt tests/workloads and needs disruption/capacity planning. Burstable t3 costs depend on CPU credits. Use realistic load and instance availability rather than assuming the cheapest advertised rate.
- Managed node groups do not add a separate node-management charge, but EC2/EBS/EKS/network still charge. EKS version support changes cost; explicitly review lifecycle before upgrades/renewals.
- A load balancer has hourly/capacity-unit/data charges even when idle. This code defaults to no LB/DNS. Avoid installing a controller that creates one implicitly before authorization.
- Logs scale with verbosity, flow volume, ingestion/query and retention. Audit/security logs matter; shorten lab TTL/retention deliberately rather than silently disabling them. No automatic budget notification destination is invented.
- Tag and track Project/Environment/Owner/ManagedBy, approve a ceiling/TTL, and configure account budget/anomaly alerts under the organization's process. Alerts are not a guaranteed spending stop. No AWS Budget resource is created because recipient/contact consent is not defined.
- State versions, ECR images, retained volumes/logs and KMS deletion windows can outlive a cluster. Verify teardown inventory and residual charges using the [operator runbook](../runbooks/aws-eks.md).
