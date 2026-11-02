variable "name" { type = string }
variable "ecr_arns" { type = list(string) }
variable "github_oidc_provider_arn" { type = string }
variable "github_repository" { type = string }
variable "github_branch" { type = string }
variable "enable_github_role" { type = bool }

resource "aws_iam_role" "cluster" {
  name = "${var.name}-cluster"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "eks.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}
resource "aws_iam_role_policy_attachment" "cluster" {
  role       = aws_iam_role.cluster.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}
resource "aws_iam_role" "node" {
  name = "${var.name}-node"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}
resource "aws_iam_role_policy_attachment" "node" {
  for_each   = toset(["AmazonEKSWorkerNodePolicy", "AmazonEC2ContainerRegistryPullOnly"])
  role       = aws_iam_role.node.name
  policy_arn = "arn:aws:iam::aws:policy/${each.key}"
}
resource "aws_iam_role" "cni" {
  name = "${var.name}-vpc-cni"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow", Principal = { Service = "pods.eks.amazonaws.com" },
      Action = ["sts:AssumeRole", "sts:TagSession"],
      Condition = { StringEquals = {
        "aws:RequestTag/eks-cluster-name"           = var.name,
        "aws:RequestTag/kubernetes-namespace"       = "kube-system",
        "aws:RequestTag/kubernetes-service-account" = "aws-node"
      } }
    }]
  })
}
resource "aws_iam_role_policy_attachment" "cni" {
  role       = aws_iam_role.cni.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}
resource "aws_iam_role" "github" {
  count                = var.enable_github_role ? 1 : 0
  name                 = "${var.name}-github-publish"
  max_session_duration = 3600
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow", Principal = { Federated = var.github_oidc_provider_arn },
      Action = "sts:AssumeRoleWithWebIdentity",
      Condition = { StringEquals = {
        "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com",
        "token.actions.githubusercontent.com:sub" = "repo:${var.github_repository}:ref:refs/heads/${var.github_branch}"
      } }
    }]
  })
}
resource "aws_iam_role_policy" "github_publish" {
  count = var.enable_github_role ? 1 : 0
  role  = aws_iam_role.github[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*"
      }, {
      Effect = "Allow",
      Action = ["ecr:BatchCheckLayerAvailability", "ecr:InitiateLayerUpload", "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload", "ecr:PutImage", "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"],
      Resource = var.ecr_arns
    }]
  })
}
output "cluster_role_arn" {
  value      = aws_iam_role.cluster.arn
  depends_on = [aws_iam_role_policy_attachment.cluster]
}
output "node_role_arn" {
  value      = aws_iam_role.node.arn
  depends_on = [aws_iam_role_policy_attachment.node]
}
output "cni_role_arn" {
  value      = aws_iam_role.cni.arn
  depends_on = [aws_iam_role_policy_attachment.cni]
}
output "github_publish_role_arn" { value = try(aws_iam_role.github[0].arn, null) }
