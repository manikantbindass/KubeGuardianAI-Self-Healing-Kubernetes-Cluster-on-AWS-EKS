variable "name" { type = string }
variable "cluster_name" { type = string }
variable "namespace" {
  type = string
  validation {
    condition     = contains(["sentinel-staging", "sentinel-production"], var.namespace)
    error_message = "Secret identity is scoped to a delivery namespace."
  }
}
variable "secret_arns" {
  type = set(string)
  validation {
    condition     = length(var.secret_arns) > 0 && alltrue([for arn in var.secret_arns : can(regex("^arn:aws:secretsmanager:[a-z0-9-]+:[0-9]{12}:secret:[A-Za-z0-9/_+=.@-]+$", arn))])
    error_message = "Supply exact approved Secrets Manager ARNs without wildcard suffixes."
  }
}
variable "kms_key_arn" {
  type = string
  validation {
    condition     = can(regex("^arn:aws:kms:[a-z0-9-]+:[0-9]{12}:key/[a-f0-9-]+$", var.kms_key_arn))
    error_message = "Use an exact customer-managed KMS key ARN."
  }
}
data "aws_region" "current" {}
resource "aws_iam_role" "secrets" {
  name = "${var.name}-secrets"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "pods.eks.amazonaws.com" },
      Action = ["sts:AssumeRole", "sts:TagSession"],
      Condition = { StringEquals = {
        "aws:RequestTag/eks-cluster-name"           = var.cluster_name,
        "aws:RequestTag/kubernetes-namespace"       = var.namespace,
        "aws:RequestTag/kubernetes-service-account" = "sentinel-secret-reader"
      } }
    }]
  })
}
resource "aws_iam_role_policy" "secrets" {
  role = aws_iam_role.secrets.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"], Resource = var.secret_arns },
      { Effect = "Allow", Action = ["kms:Decrypt"], Resource = var.kms_key_arn,
        Condition = { StringEquals = {
          "kms:ViaService"                  = "secretsmanager.${data.aws_region.current.region}.amazonaws.com",
          "kms:EncryptionContext:SecretARN" = var.secret_arns
        } }
    }]
  })
}
resource "aws_eks_pod_identity_association" "secrets" {
  cluster_name    = var.cluster_name
  namespace       = var.namespace
  service_account = "sentinel-secret-reader"
  role_arn        = aws_iam_role.secrets.arn
}
output "role_arn" { value = aws_iam_role.secrets.arn }
