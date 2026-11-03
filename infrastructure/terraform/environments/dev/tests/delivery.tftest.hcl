mock_provider "aws" {}

run "scoped_delivery_roles" {
  command = plan
  module { source = "../../modules/delivery_identity" }
  variables {
    name              = "sentinel-test"
    oidc_provider_arn = "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
    repository        = "manikantbindass/KubeSentinel-AI"
    ecr_arns          = ["arn:aws:ecr:ap-south-1:123456789012:repository/sentinel/api"]
  }
  assert {
    condition     = jsondecode(aws_iam_role.delivery["staging-publish"].assume_role_policy).Statement[0].Condition.StringEquals["token.actions.githubusercontent.com:sub"] == "repo:manikantbindass/KubeSentinel-AI:environment:staging"
    error_message = "Publishing trust must bind the exact repository and protected staging environment."
  }
  assert {
    condition     = !contains(jsondecode(aws_iam_role_policy.registry["production-verify"].policy).Statement[1].Action, "ecr:PutImage") && jsondecode(aws_iam_role_policy.registry["production-verify"].policy).Statement[1].Resource == ["arn:aws:ecr:ap-south-1:123456789012:repository/sentinel/api"]
    error_message = "Production verification may only read the exact registry repositories."
  }
  assert {
    condition     = alltrue([for action in jsondecode(aws_iam_role_policy.registry["staging-publish"].policy).Statement[1].Action : startswith(action, "ecr:")])
    error_message = "Publisher must not acquire cluster/infrastructure permissions."
  }
}

run "deny_wildcard_repository" {
  command = plan
  module { source = "../../modules/delivery_identity" }
  variables {
    name              = "sentinel-test"
    oidc_provider_arn = "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
    repository        = "owner/*"
    ecr_arns          = ["arn:aws:ecr:ap-south-1:123456789012:repository/sentinel/api"]
  }
  expect_failures = [var.repository]
}

run "scoped_secret_identity" {
  command = plan
  module { source = "../../modules/secret_identity" }
  variables {
    name         = "sentinel-staging"
    cluster_name = "sentinel-test"
    namespace    = "sentinel-staging"
    secret_arns  = ["arn:aws:secretsmanager:ap-south-1:123456789012:secret:sentinel/runtime-AbCdEf"]
    kms_key_arn  = "arn:aws:kms:ap-south-1:123456789012:key/12345678-1234-1234-1234-123456789012"
  }
  assert {
    condition     = aws_eks_pod_identity_association.secrets.namespace == "sentinel-staging" && aws_eks_pod_identity_association.secrets.service_account == "sentinel-secret-reader"
    error_message = "Secret access must bind only the dedicated environment controller account."
  }
  assert {
    condition     = jsondecode(aws_iam_role_policy.secrets.policy).Statement[0].Action == ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
    error_message = "Secret controller needs no write/list/global secret privileges."
  }
}
