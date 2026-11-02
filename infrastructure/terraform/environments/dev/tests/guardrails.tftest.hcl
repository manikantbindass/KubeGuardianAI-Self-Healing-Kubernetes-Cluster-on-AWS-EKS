mock_provider "aws" {
  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012" }
  }
  mock_data "aws_region" {
    defaults = { region = "ap-south-1" }
  }
}
variables {
  allowed_account_ids = ["123456789012"]
  owner               = "offline-test"
  name                = "sentinel-offline"
  cidr                = "10.42.0.0/16"
  availability_zones  = ["ap-south-1a", "ap-south-1b"]
  kubernetes_version  = "1.34"
  node_ami_release    = "1.34.0-20260101"
  addons = {
    vpc-cni                = "v1.0.0-eksbuild.1"
    kube-proxy             = "v1.0.0-eksbuild.1"
    coredns                = "v1.0.0-eksbuild.1"
    eks-pod-identity-agent = "v1.0.0-eksbuild.1"
  }
  autoscaling_service_linked_role_arn = "arn:aws:iam::123456789012:role/aws-service-role/autoscaling.amazonaws.com/AWSServiceRoleForAutoScaling"
}
run "private_defaults" {
  command = plan
  assert {
    condition     = module.platform.guardrails.public_api_enabled == false && module.platform.guardrails.creator_admin_enabled == false
    error_message = "Default API must be private and creator cluster-admin disabled."
  }
  assert {
    condition     = module.platform.guardrails.node_metadata_tokens == "required"
    error_message = "Nodes require IMDSv2."
  }
}
run "reject_world_access" {
  command = plan
  variables { public_access_cidrs = ["0.0.0.0/0"] }
  expect_failures = [var.public_access_cidrs]
}
run "reject_oversized_cluster" {
  command = plan
  variables { max_nodes = 100 }
  expect_failures = [var.max_nodes]
}
run "reject_no_egress" {
  command = plan
  variables {
    nat_mode         = "none"
    enable_endpoints = false
  }
  expect_failures = [var.nat_mode]
}
run "reject_wildcard_github_branch" {
  command = plan
  variables { github_branch = "*" }
  expect_failures = [var.github_branch]
}
