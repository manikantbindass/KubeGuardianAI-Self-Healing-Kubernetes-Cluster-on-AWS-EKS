# Terraform module and security reference

Phase 03 defines AWS infrastructure, not a running deployment. Root outputs are under `platform`: cluster name/endpoint, VPC/private subnets, ECR URLs, encryption key, log groups, optional roles and DNS name. No credentials, passwords, kubeconfig or database secrets are outputs.

## Environment inputs

| Input | Default / requirement |
| --- | --- |
| `region`, `allowed_account_ids`, `owner` | ap-south-1 starting region; exactly one approved account and nonempty accountable owner |
| `name`, `cidr`, `availability_zones` | Unique environment prefix, IPv4 CIDR large enough for subnet division, 2–3 distinct AZs in the chosen region |
| `nat_mode` | `single` for dev, `per_az` for demo; `none` requires private endpoints |
| `enable_endpoints` | Seven private interface services plus S3 gateway; additional hourly cost; required with no NAT |
| `kubernetes_version`, `node_ami_release`, `addons` | Explicit EKS version, compatible AL2023 x86_64 release, exact vpc-cni/kube-proxy/coredns/Pod Identity agent builds |
| `instance_types`, `capacity_type` | x86_64 t3/m6i/m7i/c6i/c7i families; t3.large, ON_DEMAND default; optional SPOT has interruption risk |
| `min_nodes`, `desired_nodes`, `max_nodes` | dev 1/1/3, demo 2/2/3; bounded to ten nodes, ordered integer sizes; no autoscaler is installed |
| `public_access_cidrs` | Empty means private-only EKS API; optional IPv4 allowlist must be /24 or narrower, never 0.0.0.0/0 |
| `view_principal_arns`, `deploy_principal_arns` | Existing role ARNs only, disjoint sets; namespace-scoped View/Edit EKS policies in `kubesentinel` |
| `autoscaling_service_linked_role_arn` | Existing AWS Auto Scaling service-linked role; key grants allow encrypted managed-node boot |
| `retention_days`, `retain_images` | 14 days dev / 30 demo logs; 30 image rollback slots, minimum ten |
| `enable_github_role`, provider ARN/repository/branch | Off by default; existing GitHub OIDC provider, exact repository and branch subject, ECR publishing only |
| `enable_workload_logs_identity` | Off by default; opt-in log-stream writer for `kubesentinel/sentinel-log-writer` only |
| `enable_dns`, zone/record/internal LB name | Off; existing zone and existing internal AWS LB endpoint; not apex alias/TLS/controller provisioning |

Public subnet CIDRs use `cidrsubnet(cidr,4,0..2)`; private use indices 8..10. Reserve that address space and check peering, service CIDR, VPN and future growth before plan. Public nodes/IPs and SSH access are not configured. Default VPC security group is emptied; EKS manages its own cluster/node security group behavior. Pod-to-pod least privilege requires the application NetworkPolicy and an enforcing VPC CNI configuration; it is not inferred from subnets.

## IAM and encryption decisions

- Cluster creator admin bootstrapping is explicitly disabled; no `AmazonEKSClusterAdminPolicy`, `system:masters`, AdministratorAccess or shared CI infrastructure administrator is created.
- View and Edit entries are namespace-scoped and reference pre-existing federated roles. Edit does **not** grant namespace/Role/RoleBinding creation. An independently authorized platform operator must create the namespace and RBAC foundations before a namespace deployer can use Helm; see the runbook's bootstrap access gate. This is deliberate separation, not automatic access recovery.
- Cluster/node/CNI use the AWS-managed EKSClusterPolicy, WorkerNodePolicy, ECR PullOnly and CNI policy required for those managed components. They are infrastructure roles, not app pod permissions. CNI networking permissions are isolated using Pod Identity rather than placed on node roles. AWS-managed policy contents can evolve; review current actions and boundaries before apply.
- CNI Pod Identity trust binds cluster, `kube-system` and `aws-node` session tags. The optional log-writer trust binds cluster/namespace/service account and permits only CreateLogStream/PutLogEvents under one log group. No model/API business role is created because it has no AWS operation to perform yet.
- The optional GitHub role accepts only `aud=sts.amazonaws.com` and `sub=repo:OWNER/REPO:ref:refs/heads/BRANCH`. It can publish to the two environment ECR repositories, cannot provision infrastructure, assume other roles or administer EKS. `ecr:GetAuthorizationToken` requires Resource `*`; repository operations are scoped to repository ARNs. Fork/PR/environment-token subjects are intentionally excluded. Protect that branch and review workflow changes. Existing account OIDC provider is required, not silently created.
- The environment KMS key rotates and protects EKS Secrets, EBS node volumes, ECR and CloudWatch groups. CloudWatch use is restricted by encryption context. The Auto Scaling service-linked role needs data-key/grant permissions for encrypted disks and must exist first. The account-root `kms:*` key-policy statement enables account IAM delegation on **this key**, not an IAM grant to all KMS keys. Resource `*` in a KMS key policy means the containing key. This is an explicit static-analysis review point.
- Terraform S3 backend uses a separate bootstrap KMS key, encryption, TLS, S3 versioning and native lockfiles. IAM state readers can see secrets stored in state; sensitive flags do not encrypt data. No actual app secrets are managed in Terraform.
- IMDSv2 is required and hop limit is one; apps cannot rely on node-role credentials. There is no SSH key or public node address. Security-group rules for AWS interface endpoints allow TLS only from private subnet CIDRs. Review EKS-created rules during the authorized plan.

## Networking and data-plane boundaries

API-to-AWS endpoints and the EKS control plane use TLS. EBS/ECR/log/state/Secrets storage encryption is defined. This code does **not** magically encrypt arbitrary pod traffic: Phase 01 uses HTTP and unauthenticated local PostgreSQL/Redis. Cloud application deployment is blocked until AuthN/AuthZ, ingress TLS and TLS database/cache URLs with certificate validation are configured. Choose `postgresql+psycopg://...?sslmode=verify-full&sslrootcert=...` and `rediss://...` with trusted CA handling; never disable certificate verification to pass smoke.

Private endpoint mode creates ecr.api, ecr.dkr, sts, eks, eks-auth, logs and ec2 interface endpoints in each private AZ plus an S3 gateway. The endpoint security group restricts clients; endpoint policies are AWS defaults and need workload/account restrictions in a production review. No-NAT mode cannot pull Docker Hub images or contact arbitrary providers: mirror dependencies to approved ECR and supply additional endpoints if requirements change. Endpoint services/AZ support need regional validation.

Load balancing is deliberately opt-in and separate: no controller IAM or public LB is created. After an approved internal controller/TLS deployment supplies a hostname, optional DNS creates a CNAME in an existing private hosted zone. A data-source postcondition rejects public zones during an authorized plan. The code requires an internal LB hostname and does not expose an application or grant controller authority.

CloudWatch creates control-plane, VPC flow and optional workload destination groups, plus an audit-403 log metric/alarm. No workload collector is installed; log-writer identity alone does not send logs. The alarm has no destination until notification ownership is separately configured, and missing data is not proof of health. Managed service logs, log filter schema and alarm behavior require live acceptance tests after an approved deployment.
