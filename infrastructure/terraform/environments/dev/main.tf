variable "region" {
  type    = string
  default = "ap-south-1"
  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-[0-9]$", var.region))
    error_message = "Use a commercial AWS region identifier."
  }
}
variable "allowed_account_ids" {
  type = list(string)
  validation {
    condition     = length(var.allowed_account_ids) == 1 && can(regex("^[0-9]{12}$", var.allowed_account_ids[0]))
    error_message = "Pin exactly one approved target account."
  }
}
variable "owner" {
  type = string
  validation {
    condition     = length(trimspace(var.owner)) > 0
    error_message = "An accountable owner is required."
  }
}
provider "aws" {
  region              = var.region
  allowed_account_ids = var.allowed_account_ids
  default_tags {
    tags = { Project = "KubeSentinel-AI", Environment = "dev", Owner = var.owner, ManagedBy = "Terraform" }
  }
}
module "platform" {
  source                              = "../../modules/platform"
  name                                = var.name
  cidr                                = var.cidr
  availability_zones                  = var.availability_zones
  nat_mode                            = var.nat_mode
  enable_endpoints                    = var.enable_endpoints
  retention_days                      = var.retention_days
  retain_images                       = var.retain_images
  kubernetes_version                  = var.kubernetes_version
  node_ami_release                    = var.node_ami_release
  instance_types                      = var.instance_types
  capacity_type                       = var.capacity_type
  min_nodes                           = var.min_nodes
  max_nodes                           = var.max_nodes
  desired_nodes                       = var.desired_nodes
  public_access_cidrs                 = var.public_access_cidrs
  addons                              = var.addons
  autoscaling_service_linked_role_arn = var.autoscaling_service_linked_role_arn
  view_principal_arns                 = var.view_principal_arns
  deploy_principal_arns               = var.deploy_principal_arns
  enable_delivery_roles               = var.enable_delivery_roles
  enable_github_role                  = var.enable_github_role
  github_oidc_provider_arn            = var.github_oidc_provider_arn
  github_repository                   = var.github_repository
  github_branch                       = var.github_branch
  enable_workload_logs_identity       = var.enable_workload_logs_identity
  enable_dns                          = var.enable_dns
  dns_zone_id                         = var.dns_zone_id
  dns_record_name                     = var.dns_record_name
  internal_load_balancer_dns_name     = var.internal_load_balancer_dns_name
}
output "platform" { value = {
  cluster_name            = module.platform.cluster_name
  endpoint                = module.platform.cluster_endpoint
  vpc_id                  = module.platform.vpc_id
  private_subnet_ids      = module.platform.private_subnet_ids
  ecr_urls                = module.platform.ecr_urls
  kms_key_arn             = module.platform.kms_key_arn
  github_publish_role_arn = module.platform.github_publish_role_arn
  workload_log_role_arn   = module.platform.workload_log_role_arn
  log_groups              = module.platform.log_groups
  dns_name                = module.platform.dns_name
} }

output "delivery_roles" { value = module.platform.delivery_roles }
