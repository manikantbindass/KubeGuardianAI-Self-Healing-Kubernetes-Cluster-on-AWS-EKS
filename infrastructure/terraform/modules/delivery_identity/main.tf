variable "name" { type = string }
variable "oidc_provider_arn" {
  type = string
  validation {
    condition     = can(regex("^arn:aws:iam::[0-9]{12}:oidc-provider/token.actions.githubusercontent.com$", var.oidc_provider_arn))
    error_message = "Use the account's existing GitHub OIDC provider ARN."
  }
}
variable "repository" {
  type = string
  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.repository))
    error_message = "Use an exact owner/repository without wildcards."
  }
}
variable "ecr_arns" {
  type = list(string)
  validation {
    condition     = length(var.ecr_arns) > 0 && alltrue([for arn in var.ecr_arns : can(regex("^arn:aws:ecr:[a-z0-9-]+:[0-9]{12}:repository/[a-z0-9/-]+$", arn))])
    error_message = "Use exact ECR repository ARNs; wildcards are forbidden."
  }
}

locals {
  roles = {
    staging-publish   = { environment = "staging", publish = true }
    staging-verify    = { environment = "staging", publish = false }
    production-verify = { environment = "production", publish = false }
  }
}
resource "aws_iam_role" "delivery" {
  for_each             = local.roles
  name                 = "${var.name}-${each.key}"
  max_session_duration = 3600
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow", Principal = { Federated = var.oidc_provider_arn },
      Action = "sts:AssumeRoleWithWebIdentity",
      Condition = { StringEquals = {
        "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com",
        "token.actions.githubusercontent.com:sub" = "repo:${var.repository}:environment:${each.value.environment}"
      } }
    }]
  })
}
resource "aws_iam_role_policy" "registry" {
  for_each = local.roles
  role     = aws_iam_role.delivery[each.key].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*"
      }, {
      Effect = "Allow", Resource = var.ecr_arns,
      Action = concat(["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"],
      each.value.publish ? ["ecr:InitiateLayerUpload", "ecr:UploadLayerPart", "ecr:CompleteLayerUpload", "ecr:PutImage"] : [])
    }]
  })
}
output "roles" { value = { for name, role in aws_iam_role.delivery : name => role.arn } }
