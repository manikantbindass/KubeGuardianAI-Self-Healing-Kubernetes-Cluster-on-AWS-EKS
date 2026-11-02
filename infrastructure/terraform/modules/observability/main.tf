variable "name" { type = string }
variable "retention_days" { type = number }
variable "kms_key_arn" { type = string }
variable "cluster_name" { type = string }
resource "aws_cloudwatch_log_group" "control_plane" {
  name              = "/aws/eks/${var.cluster_name}/cluster"
  retention_in_days = var.retention_days
  kms_key_id        = var.kms_key_arn
}
resource "aws_cloudwatch_log_group" "flows" {
  name              = "/kubesentinel/${var.name}/vpc-flows"
  retention_in_days = var.retention_days
  kms_key_id        = var.kms_key_arn
}
resource "aws_cloudwatch_log_group" "workloads" {
  name              = "/kubesentinel/${var.name}/workloads"
  retention_in_days = var.retention_days
  kms_key_id        = var.kms_key_arn
}
resource "aws_iam_role" "flows" {
  name = "${var.name}-flow-logs"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "vpc-flow-logs.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}
resource "aws_iam_role_policy" "flows" {
  role = aws_iam_role.flows.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"]
      Resource = ["${aws_cloudwatch_log_group.flows.arn}:*"]
    }]
  })
}
resource "aws_cloudwatch_log_metric_filter" "forbidden" {
  name           = "${var.name}-forbidden"
  log_group_name = aws_cloudwatch_log_group.control_plane.name
  pattern        = "{ $.responseStatus.code = 403 }"
  metric_transformation {
    name      = "ForbiddenRequests"
    namespace = "KubeSentinel/${var.name}"
    value     = "1"
  }
}
resource "aws_cloudwatch_metric_alarm" "api_errors" {
  alarm_name          = "${var.name}-eks-api-errors"
  namespace           = "KubeSentinel/${var.name}"
  metric_name         = "ForbiddenRequests"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 2
  threshold           = 100
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
}
output "flow_log_group_arn" { value = aws_cloudwatch_log_group.flows.arn }
output "flow_log_role_arn" { value = aws_iam_role.flows.arn }
output "workload_log_group_arn" { value = aws_cloudwatch_log_group.workloads.arn }
output "log_groups" { value = [aws_cloudwatch_log_group.control_plane.name, aws_cloudwatch_log_group.flows.name, aws_cloudwatch_log_group.workloads.name] }
