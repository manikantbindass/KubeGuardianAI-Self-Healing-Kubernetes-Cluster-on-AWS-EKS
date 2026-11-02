# Remote state bootstrap and locking

This runbook does not authorize apply/destroy. Bootstrap resources incur cost and require separate explicit approval. Do not run bootstrap just to validate code.

## Separate owner-approved bootstrap

The `infrastructure/terraform/bootstrap` root creates an S3 bucket, public-access block, owner-enforced objects, versioning, TLS-only bucket policy and default KMS encryption with rotation. Bucket and KMS key have `prevent_destroy`; force-destroy is false. It initially uses local Terraform state. That local state contains sensitive identifiers and must be encrypted/protected, backed up securely and later migrated to a separately controlled backend by an authorized operator. Never commit it. State resources must not share a lifecycle with an ephemeral EKS demo.

Before an approved bootstrap: choose a globally unique bucket, approved account/region and owner; review KMS administration/recovery and access policy, budget, audit logging/retention, bootstrap credentials and saved plan. Use the `.tfvars.example` only as a template; no example account/name is deployable. Run `terraform init` and `terraform plan` in that root only with approved credentials. Stop for plan/cost approval; execution is a separate operator action. This agent has not performed either bootstrap planning or execution against AWS.

## Environment backend

Copy `backend.hcl.example` to ignored `backend.hcl` in each environment and replace bucket/key/region/KMS ARN. Each environment has a separate key, preferably a separate account/bucket/key for stronger isolation. The backend is partial configuration and cannot use Terraform variables. Never put credentials, session tokens or role secrets in backend files: initialization can cache backend configuration under `.terraform` and plan artifacts.

```sh
terraform -chdir=infrastructure/terraform/environments/dev init -reconfigure -backend-config=backend.hcl
```

Only run this after bootstrap and credential approval. Backend access uses TLS, `encrypt=true`, a customer-managed state key and `use_lockfile=true` (Terraform 1.10+). DynamoDB locking is not required for this selected toolchain. Never set `-lock=false` to bypass a teammate's lock.

## Least-privilege backend access contract

An account administrator should grant a state operator:

- `s3:ListBucket` on the exact bucket with a prefix condition for the environment state/lock path.
- `s3:GetObject` and `s3:PutObject` on the exact environment state key; ordinary operations do not need state deletion.
- `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` on the corresponding `.tflock` key.
- `kms:Encrypt`, `kms:Decrypt`, `kms:GenerateDataKey`, `kms:DescribeKey` on the state KMS key with appropriate S3 service/context restrictions and key-policy permission.

Separate state recovery/version deletion privileges from ordinary planning. Use short-lived federated sessions, audited access and restricted plan artifacts. S3 lock objects must remain deletable by authorized runners; do not blanket Object Lock retention on `.tflock` files. Configure archival retention for state versions according to recovery/security requirements. Versioning is not an independently tested backup.

If a command stops: confirm no live Terraform process owns the lock, inspect lock metadata and obtain operator approval before `force-unlock`. Never delete lock/state objects blindly. Restore a state version only after a reviewed recovery plan and verification of actual resources. Do not manually edit state to make teardown appear complete.

References: [HashiCorp S3 backend](https://developer.hashicorp.com/terraform/language/backend/s3), [sensitive state guidance](https://developer.hashicorp.com/terraform/language/manage-sensitive-data).
