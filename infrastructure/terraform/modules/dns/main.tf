variable "enabled" { type = bool }
variable "zone_id" { type = string }
variable "record_name" { type = string }
variable "internal_load_balancer_dns_name" { type = string }
data "aws_route53_zone" "this" {
  count   = var.enabled ? 1 : 0
  zone_id = var.zone_id
  lifecycle {
    postcondition {
      condition     = self.private_zone
      error_message = "Only an existing private hosted zone is allowed."
    }
  }
}
resource "aws_route53_record" "this" {
  count   = var.enabled ? 1 : 0
  zone_id = data.aws_route53_zone.this[0].zone_id
  name    = var.record_name
  type    = "CNAME"
  ttl     = 60
  records = [var.internal_load_balancer_dns_name]
}
output "fqdn" { value = try(aws_route53_record.this[0].fqdn, null) }
