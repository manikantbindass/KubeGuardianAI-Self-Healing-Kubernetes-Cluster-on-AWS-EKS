# Local versus cloud capability matrix

| Capability | Phase 02 local kind | Phase 03 AWS code |
| --- | --- | --- |
| Cluster lifecycle | Tested fresh kind bootstrap and scoped deletion | Terraform EKS resources; no AWS apply/destroy or live plan |
| Compute | Docker-backed nodes | Private managed AL2023 x86_64 EC2 nodes, explicit AMI/add-on pins, IMDSv2 and encrypted disks |
| Images | Built/loaded local tags | KMS ECR repos, immutable tags, scan-on-push; publishing workflow/operator step separate |
| Access | Loopback port-forward | Private API and explicit existing IAM role access entries; no creator/CI cluster-admin |
| App status/greetings | Real frontend/API/worker smoke passes | Infrastructure only; same chart mappings below, cloud app deployment not verified |
| Durable stores | Lab PostgreSQL/Redis PVCs | External TLS stores required for dev/prod chart profiles; RDS/ElastiCache not provisioned |
| Identity | App unauthenticated | AWS IAM/Pod Identity infrastructure only; product OIDC/RBAC still absent |
| Logs | Container logs, worker/API JSON | Encrypted control-plane/flow log plumbing; workload destination/optional scoped identity; no collector installed |
| Ingress / DNS | Port-forward tested; ingress schema only | Optional existing internal LB CNAME; no controller, public LB, certificate or TLS app endpoint |
| NetworkPolicy | Negative isolation test passed in kind | Requires VPC CNI network policy configuration/controller compatibility and external-service allowances; unverified on EKS |
| HPA | Template only, disabled without metrics | Same; no metrics-server/autoscaler deployed |
| GitOps | Not installed | No Argo CD/Flux/cluster write credentials provisioned |
| Costs | Local host resources | Paid resources only after separate plan/cost/apply approval |

## Helm and environment mapping

Use `values-dev.yaml` or `values-prod.yaml` with `localStores=false`, separately created Secret, and unique ECR commit tags. Terraform output `platform.ecr_urls.api` serves API, worker and migrator; `platform.ecr_urls.dashboard` serves Next.js. The chart's **shared tag** requires publishing the same commit tag to both repositories. Service DNS remains `http://sentinel-api:8000` for server-side Next.js; that internal HTTP hop needs a reviewed TLS/mesh solution before production. Do not expose it as a browser `NEXT_PUBLIC_*` URL.

| Helm / API setting | Source / requirement |
| --- | --- |
| `image.api`, `image.dashboard`, `image.tag` | Terraform repository URLs + immutable reviewed commit tag |
| `image.pullPolicy` | IfNotPresent is acceptable with immutable tags; production admission/digest policy still needed |
| `secretName` | Existing namespace Secret; no secrets in Terraform/Helm values |
| `DATABASE_URL` | Secret containing psycopg PostgreSQL URL, verify-full and trusted CA configuration |
| `REDIS_URL` | Secret containing authenticated rediss URL with trusted certificate handling |
| `POSTGRES_PASSWORD` | Only required by localStores=true; not consumed by external-store app pods |
| `environment`, `CORS_ORIGINS` | Cloud profile environment; trusted origin list must match the eventual authenticated TLS endpoint |
| `resources`, `replicas`, PDB | Capacity and disruption review against node bounds; chart has no topology-spread guarantee |
| Pod Identity | Optional `sentinel-log-writer` is a separate identity, not the default `sentinel` API account; no log collector is created |

The chart permits app-labelled namespace peers and DNS by default. `networkPolicy.extraEgress` and `extraIngress` accept explicit Kubernetes policy rules for reviewed DB/cache endpoints, identity/log egress and ingress-controller selectors; both default empty. `corsOrigins` is the exact JSON-origin list consumed by FastAPI. Dev/prod set `rbac.create=false`; an authorized platform operator must create the observer Role/RoleBinding before namespace deployers use Helm. Local still creates its tested scoped RBAC.

Do not disable isolation or add unrestricted 0.0.0.0/0 egress to make deployment pass. Private subnets alone do not enforce pod tenancy. Helm/kubeconform validate syntax, not AWS reachability or TLS. Pod Identity uses link-local agent addresses; test CNI handling and allow only required identity/HTTPS destinations before enabling the log writer.
