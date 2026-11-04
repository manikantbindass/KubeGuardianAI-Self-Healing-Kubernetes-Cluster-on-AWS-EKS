variable "name" { type = string }
variable "kubernetes_version" { type = string }
variable "subnet_ids" { type = list(string) }
data "aws_default_tags" "current" {}
variable "cluster_role_arn" { type = string }
variable "node_role_arn" { type = string }
variable "cni_role_arn" { type = string }
variable "kms_key_arn" { type = string }
variable "public_access_cidrs" { type = list(string) }
variable "instance_types" { type = list(string) }
variable "capacity_type" { type = string }
variable "node_ami_release" { type = string }
variable "min_nodes" { type = number }
variable "max_nodes" { type = number }
variable "desired_nodes" { type = number }
variable "addons" { type = map(string) }
variable "view_principal_arns" { type = set(string) }
variable "deploy_principal_arns" { type = set(string) }

resource "aws_eks_cluster" "this" {
  name                          = var.name
  role_arn                      = var.cluster_role_arn
  version                       = var.kubernetes_version
  enabled_cluster_log_types     = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
  bootstrap_self_managed_addons = false
  access_config {
    authentication_mode                         = "API"
    bootstrap_cluster_creator_admin_permissions = false
  }
  vpc_config {
    subnet_ids              = var.subnet_ids
    endpoint_private_access = true
    endpoint_public_access  = length(var.public_access_cidrs) > 0
    public_access_cidrs     = var.public_access_cidrs
  }
  encryption_config {
    provider { key_arn = var.kms_key_arn }
    resources = ["secrets"]
  }
  upgrade_policy { support_type = "STANDARD" }
}
resource "aws_launch_template" "node" {
  name_prefix            = "${var.name}-"
  update_default_version = true
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "disabled"
  }
  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size           = 30
      volume_type           = "gp3"
      encrypted             = true
      kms_key_id            = var.kms_key_arn
      delete_on_termination = true
    }
  }
  tag_specifications {
    resource_type = "instance"
    tags          = merge(data.aws_default_tags.current.tags, { Name = "${var.name}-worker" })
  }
  tag_specifications {
    resource_type = "volume"
    tags          = merge(data.aws_default_tags.current.tags, { Name = "${var.name}-worker-volume" })
  }
}
resource "aws_eks_addon" "before_compute" {
  for_each                    = { for name, version in var.addons : name => version if name != "coredns" }
  cluster_name                = aws_eks_cluster.this.name
  addon_name                  = each.key
  addon_version               = each.value
  resolve_conflicts_on_update = "PRESERVE"
  configuration_values        = each.key == "vpc-cni" ? jsonencode({ enableNetworkPolicy = "true" }) : null
  dynamic "pod_identity_association" {
    for_each = each.key == "vpc-cni" ? [1] : []
    content {
      role_arn        = var.cni_role_arn
      service_account = "aws-node"
    }
  }
}
resource "aws_eks_node_group" "this" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${var.name}-managed"
  node_role_arn   = var.node_role_arn
  subnet_ids      = var.subnet_ids
  instance_types  = var.instance_types
  ami_type        = "AL2023_x86_64_STANDARD"
  release_version = var.node_ami_release
  version         = var.kubernetes_version
  capacity_type   = var.capacity_type
  launch_template {
    id      = aws_launch_template.node.id
    version = aws_launch_template.node.latest_version
  }
  scaling_config {
    min_size     = var.min_nodes
    max_size     = var.max_nodes
    desired_size = var.desired_nodes
  }
  update_config { max_unavailable = 1 }
  depends_on = [aws_eks_addon.before_compute]
}
resource "aws_eks_addon" "dns" {
  cluster_name                = aws_eks_cluster.this.name
  addon_name                  = "coredns"
  addon_version               = var.addons["coredns"]
  resolve_conflicts_on_update = "PRESERVE"
  depends_on                  = [aws_eks_node_group.this]
}
resource "aws_eks_access_entry" "viewer" {
  for_each      = var.view_principal_arns
  cluster_name  = aws_eks_cluster.this.name
  principal_arn = each.value
  type          = "STANDARD"
}
resource "aws_eks_access_policy_association" "viewer" {
  for_each      = aws_eks_access_entry.viewer
  cluster_name  = aws_eks_cluster.this.name
  principal_arn = each.value.principal_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSViewPolicy"
  access_scope {
    type       = "namespace"
    namespaces = ["kubesentinel"]
  }
}
resource "aws_eks_access_entry" "deployer" {
  for_each      = var.deploy_principal_arns
  cluster_name  = aws_eks_cluster.this.name
  principal_arn = each.value
  type          = "STANDARD"
}
resource "aws_eks_access_policy_association" "deployer" {
  for_each      = aws_eks_access_entry.deployer
  cluster_name  = aws_eks_cluster.this.name
  principal_arn = each.value.principal_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSEditPolicy"
  access_scope {
    type       = "namespace"
    namespaces = ["kubesentinel"]
  }
}
output "cluster_name" { value = aws_eks_cluster.this.name }
output "cluster_arn" { value = aws_eks_cluster.this.arn }
output "endpoint" { value = aws_eks_cluster.this.endpoint }
output "security_group_id" { value = aws_eks_cluster.this.vpc_config[0].cluster_security_group_id }
output "public_api_enabled" { value = aws_eks_cluster.this.vpc_config[0].endpoint_public_access }
output "creator_admin_enabled" { value = aws_eks_cluster.this.access_config[0].bootstrap_cluster_creator_admin_permissions }
output "node_metadata_tokens" { value = aws_launch_template.node.metadata_options[0].http_tokens }
