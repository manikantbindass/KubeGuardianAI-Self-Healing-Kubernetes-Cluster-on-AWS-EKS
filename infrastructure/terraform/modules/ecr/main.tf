variable "name" { type = string }
variable "kms_key_arn" { type = string }
variable "retain_images" {
  type = number
  validation {
    condition     = var.retain_images >= 10
    error_message = "Keep at least ten images for rollback."
  }
}
resource "aws_ecr_repository" "this" {
  for_each             = toset(["api", "dashboard", "operator", "detector", "demo-workload"])
  name                 = "${var.name}/${each.key}"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false
  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = var.kms_key_arn
  }
  image_scanning_configuration { scan_on_push = true }
}
resource "aws_ecr_lifecycle_policy" "this" {
  for_each   = aws_ecr_repository.this
  repository = each.value.name
  policy = jsonencode({ rules = [{
    rulePriority = 1, description = "Retain untagged images for seven days",
    selection    = { tagStatus = "untagged", countType = "sinceImagePushed", countUnit = "days", countNumber = 7 },
    action       = { type = "expire" }
    }, {
    rulePriority = 2, description = "Bound tagged image retention; review rollback requirements",
    selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = var.retain_images },
    action       = { type = "expire" }
  }] })
}
output "arns" { value = [for repo in aws_ecr_repository.this : repo.arn] }
output "urls" { value = { for key, repo in aws_ecr_repository.this : key => repo.repository_url } }
