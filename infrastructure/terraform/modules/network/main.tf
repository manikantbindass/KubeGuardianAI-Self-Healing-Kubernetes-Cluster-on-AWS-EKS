variable "name" { type = string }
variable "cidr" { type = string }
variable "availability_zones" { type = list(string) }
variable "nat_mode" {
  type = string
  validation {
    condition     = contains(["none", "single", "per_az"], var.nat_mode)
    error_message = "nat_mode must be none, single or per_az."
  }
}
variable "enable_endpoints" { type = bool }
variable "flow_log_group_arn" { type = string }
variable "flow_log_role_arn" { type = string }

resource "aws_vpc" "this" {
  cidr_block           = var.cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = var.name }
}
resource "aws_default_security_group" "this" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${var.name}-unused-default" }
}
resource "aws_internet_gateway" "this" { vpc_id = aws_vpc.this.id }
resource "aws_subnet" "public" {
  count                   = length(var.availability_zones)
  vpc_id                  = aws_vpc.this.id
  availability_zone       = var.availability_zones[count.index]
  cidr_block              = cidrsubnet(var.cidr, 4, count.index)
  map_public_ip_on_launch = false
  tags                    = { Name = "${var.name}-public-${count.index}", "kubernetes.io/role/elb" = "1" }
}
resource "aws_subnet" "private" {
  count                   = length(var.availability_zones)
  vpc_id                  = aws_vpc.this.id
  availability_zone       = var.availability_zones[count.index]
  cidr_block              = cidrsubnet(var.cidr, 4, count.index + 8)
  map_public_ip_on_launch = false
  tags                    = { Name = "${var.name}-private-${count.index}", "kubernetes.io/role/internal-elb" = "1" }
}
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${var.name}-public" }
}
resource "aws_route" "internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.this.id
}
resource "aws_route_table_association" "public" {
  count          = length(var.availability_zones)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}
resource "aws_eip" "nat" {
  count  = var.nat_mode == "none" ? 0 : var.nat_mode == "single" ? 1 : length(var.availability_zones)
  domain = "vpc"
}
resource "aws_nat_gateway" "this" {
  count         = length(aws_eip.nat)
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  depends_on    = [aws_internet_gateway.this]
}
resource "aws_route_table" "private" {
  count  = length(var.availability_zones)
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${var.name}-private-${count.index}" }
}
resource "aws_route" "nat" {
  count                  = var.nat_mode == "none" ? 0 : length(var.availability_zones)
  route_table_id         = aws_route_table.private[count.index].id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.this[var.nat_mode == "single" ? 0 : count.index].id
}
resource "aws_route_table_association" "private" {
  count          = length(var.availability_zones)
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}
data "aws_region" "current" {}
resource "aws_security_group" "endpoints" {
  count       = var.enable_endpoints ? 1 : 0
  name_prefix = "${var.name}-endpoints-"
  description = "TLS to private AWS service endpoints"
  vpc_id      = aws_vpc.this.id
  ingress {
    description = "Private subnet HTTPS clients"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = aws_subnet.private[*].cidr_block
  }
}
resource "aws_vpc_endpoint" "interface" {
  for_each            = var.enable_endpoints ? toset(["ecr.api", "ecr.dkr", "sts", "eks", "eks-auth", "logs", "ec2"]) : toset([])
  vpc_id              = aws_vpc.this.id
  service_name        = "com.amazonaws.${data.aws_region.current.region}.${each.key}"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.endpoints[0].id]
}
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.this.id
  service_name      = "com.amazonaws.${data.aws_region.current.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = aws_route_table.private[*].id
}
resource "aws_flow_log" "this" {
  vpc_id               = aws_vpc.this.id
  traffic_type         = "ALL"
  log_destination_type = "cloud-watch-logs"
  log_destination      = var.flow_log_group_arn
  iam_role_arn         = var.flow_log_role_arn
}
output "vpc_id" { value = aws_vpc.this.id }
output "private_subnet_ids" { value = aws_subnet.private[*].id }
output "public_subnet_ids" { value = aws_subnet.public[*].id }
