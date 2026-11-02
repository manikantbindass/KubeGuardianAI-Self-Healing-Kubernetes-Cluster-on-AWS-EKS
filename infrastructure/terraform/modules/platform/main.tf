data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
resource "aws_kms_key" "this" {
  description             = "KubeSentinel ${var.name} encryption key"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "AccountKeyAdministration",
      Effect = "Allow", Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root" },
      Action = "kms:*", Resource = "*"
      }, {
      Sid      = "EncryptedCloudWatchGroups",
      Effect   = "Allow", Principal = { Service = "logs.${data.aws_region.current.region}.amazonaws.com" },
      Action   = ["kms:Encrypt", "kms:Decrypt", "kms:ReEncrypt*", "kms:GenerateDataKey*", "kms:DescribeKey"],
      Resource = "*",
      Condition = { ArnLike = { "kms:EncryptionContext:aws:logs:arn" = [
        "arn:aws:logs:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/eks/${var.name}/cluster",
        "arn:aws:logs:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:log-group:/kubesentinel/${var.name}/*"
      ] } }
      }, {
      Sid      = "EncryptedManagedNodeVolumes",
      Effect   = "Allow", Principal = { AWS = var.autoscaling_service_linked_role_arn },
      Action   = ["kms:Encrypt", "kms:Decrypt", "kms:ReEncrypt*", "kms:GenerateDataKey*", "kms:DescribeKey"],
      Resource = "*"
      }, {
      Sid       = "ManagedNodeGrants",
      Effect    = "Allow", Principal = { AWS = var.autoscaling_service_linked_role_arn },
      Action    = ["kms:CreateGrant"], Resource = "*",
      Condition = { Bool = { "kms:GrantIsForAWSResource" = "true" } }
    }]
  })
}
resource "aws_kms_alias" "this" {
  name          = "alias/${var.name}"
  target_key_id = aws_kms_key.this.key_id
}
module "observability" {
  source         = "../observability"
  name           = var.name
  cluster_name   = var.name
  retention_days = var.retention_days
  kms_key_arn    = aws_kms_key.this.arn
}
module "network" {
  source             = "../network"
  name               = var.name
  cidr               = var.cidr
  availability_zones = var.availability_zones
  nat_mode           = var.nat_mode
  enable_endpoints   = var.enable_endpoints
  flow_log_group_arn = module.observability.flow_log_group_arn
  flow_log_role_arn  = module.observability.flow_log_role_arn
}
module "ecr" {
  source        = "../ecr"
  name          = var.name
  kms_key_arn   = aws_kms_key.this.arn
  retain_images = var.retain_images
}
module "iam" {
  source                   = "../iam"
  name                     = var.name
  ecr_arns                 = module.ecr.arns
  enable_github_role       = var.enable_github_role
  github_repository        = var.github_repository
  github_branch            = var.github_branch
  github_oidc_provider_arn = var.github_oidc_provider_arn
}
module "eks" {
  source                = "../eks"
  name                  = var.name
  kubernetes_version    = var.kubernetes_version
  subnet_ids            = module.network.private_subnet_ids
  cluster_role_arn      = module.iam.cluster_role_arn
  node_role_arn         = module.iam.node_role_arn
  cni_role_arn          = module.iam.cni_role_arn
  kms_key_arn           = aws_kms_key.this.arn
  public_access_cidrs   = var.public_access_cidrs
  instance_types        = var.instance_types
  capacity_type         = var.capacity_type
  node_ami_release      = var.node_ami_release
  min_nodes             = var.min_nodes
  max_nodes             = var.max_nodes
  desired_nodes         = var.desired_nodes
  addons                = var.addons
  view_principal_arns   = var.view_principal_arns
  deploy_principal_arns = var.deploy_principal_arns
  depends_on            = [module.observability]
}
module "workload_identity" {
  source          = "../workload_identity"
  name            = var.name
  cluster_name    = module.eks.cluster_name
  log_group_arn   = module.observability.workload_log_group_arn
  enabled         = var.enable_workload_logs_identity
  namespace       = "kubesentinel"
  service_account = "sentinel-log-writer"
  depends_on      = [module.eks]
}
module "dns" {
  source                          = "../dns"
  enabled                         = var.enable_dns
  zone_id                         = var.dns_zone_id
  record_name                     = var.dns_record_name
  internal_load_balancer_dns_name = var.internal_load_balancer_dns_name
}
check "network_access" {
  assert {
    condition     = var.nat_mode != "none" || var.enable_endpoints
    error_message = "No-NAT private nodes require private AWS endpoints."
  }
}
check "scaling" {
  assert {
    condition     = var.min_nodes <= var.desired_nodes && var.desired_nodes <= var.max_nodes
    error_message = "Require min_nodes <= desired_nodes <= max_nodes."
  }
}
output "cluster_name" { value = module.eks.cluster_name }
output "cluster_endpoint" { value = module.eks.endpoint }
output "vpc_id" { value = module.network.vpc_id }
output "private_subnet_ids" { value = module.network.private_subnet_ids }
output "ecr_urls" { value = module.ecr.urls }
output "github_publish_role_arn" { value = module.iam.github_publish_role_arn }
output "workload_log_role_arn" { value = module.workload_identity.role_arn }
output "log_groups" { value = module.observability.log_groups }
output "kms_key_arn" { value = aws_kms_key.this.arn }
output "dns_name" { value = module.dns.fqdn }
output "guardrails" {
  value = {
    public_api_enabled    = module.eks.public_api_enabled
    creator_admin_enabled = module.eks.creator_admin_enabled
    node_metadata_tokens  = module.eks.node_metadata_tokens
  }
}
