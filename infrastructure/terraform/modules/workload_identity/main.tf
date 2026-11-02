variable "name" { type = string }
variable "cluster_name" { type = string }
variable "log_group_arn" { type = string }
variable "enabled" { type = bool }
variable "namespace" { type = string }
variable "service_account" { type = string }
resource "aws_iam_role" "logs" {
  count = var.enabled ? 1 : 0
  name  = "${var.name}-workload-logs"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow", Principal = { Service = "pods.eks.amazonaws.com" },
      Action = ["sts:AssumeRole", "sts:TagSession"],
      Condition = { StringEquals = {
        "aws:RequestTag/eks-cluster-name"           = var.cluster_name,
        "aws:RequestTag/kubernetes-namespace"       = var.namespace,
        "aws:RequestTag/kubernetes-service-account" = var.service_account
      } }
    }]
  })
}
resource "aws_iam_role_policy" "logs" {
  count = var.enabled ? 1 : 0
  role  = aws_iam_role.logs[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"],
      Resource = ["${var.log_group_arn}:*"]
    }]
  })
}
resource "aws_eks_pod_identity_association" "logs" {
  count           = var.enabled ? 1 : 0
  cluster_name    = var.cluster_name
  namespace       = var.namespace
  service_account = var.service_account
  role_arn        = aws_iam_role.logs[0].arn
}
output "role_arn" { value = try(aws_iam_role.logs[0].arn, null) }
