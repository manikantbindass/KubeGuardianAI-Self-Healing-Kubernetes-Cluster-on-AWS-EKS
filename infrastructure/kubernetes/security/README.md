# Optional delivery security integration

These are administrator-installed examples; they are not automatically applied by the application chart or cloud workflows.

`digest-admission.yaml` is native Kubernetes 1.30+ ValidatingAdmissionPolicy/Binding. Only namespaces labeled `delivery.kubesentinel.ai/enforce=true` match. Set the administrator-owned namespace annotation `delivery.kubesentinel.ai/registry-prefix` to the exact approved ECR registry/project prefix. Missing annotation fails closed. The policy rejects mutable/foreign container and init-container images and ephemeral containers; it does not verify cryptographic signatures. Enforce namespace Pod Security `restricted` and restrict who can change namespace labels/annotations or admission policies. The disposable kind test exercises actual API admission; no production policy is installed by CI.

`external-secrets.example.yaml` references AWS Secrets Manager paths and never contains secret values. Install a reviewed, pinned External Secrets controller/CRDs with API `external-secrets.io/v1`. Use a **dedicated namespace-scoped** controller in `sentinel-staging`, controller class `sentinel-staging`, and service account `sentinel-secret-reader` with no controller-wide secret access. Its AWS SDK default credential chain uses EKS Pod Identity: instantiate Terraform module `secret_identity` with exact secret ARNs, namespace, cluster and customer-managed KMS key. The module's association binds that service account; the application account gets no AWS credentials. SecretStore `controller` must match the installed controller class. Repeat with a separate controller/role/paths for production.

Configure these existing JSON secrets out of band through an approved secret manager:

| Path suffix | Expected keys |
| --- | --- |
| `runtime` | `DATABASE_URL`, `REDIS_URL` (and any required database connection configuration) |
| `operations-api` | `OPS_BRIDGE_TOKEN`; local development tokens must not be supplied in cloud mode |
| `operations-web` | `APP_SESSION_SECRET`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET` as required by the provider |

Verify actual [operations configuration](../../../docs/runbooks/operations-dashboard.md) names before populating secrets. Signing key material needs a separately protected `sentinel-approver` Secret mounted by the existing chart option; never expose it to the dashboard. Set operations `approvalSecretName` only after configuring the operator's matching trusted public key. External Secrets reconciliation is not part of the namespace application AppProject allowlist; the platform team owns it.

Use TLS-enabled external stores, namespace/network restrictions and approved OIDC/telemetry egress. The SecretStore needs explicit Secrets Manager/KMS network access; cloud credentials do not bypass NetworkPolicy. Review controller IAM, CRD version, refresh behavior and namespace-scoped Kubernetes RBAC before installing. Rotation of environment variables requires controlled workload restart; CSI-mounted secrets are an alternative when the application can reload files. No live AWS secret retrieval or controller installation is claimed by this phase.
