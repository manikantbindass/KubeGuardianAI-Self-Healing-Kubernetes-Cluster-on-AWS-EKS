variable "name" {
  description = "name; see the module reference for restrictions."
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,35}$", var.name))
    error_message = "Invalid name; review documented scope, pins and safety limits."
  }
}
variable "cidr" {
  description = "cidr; see the module reference for restrictions."
  type        = string
  validation {
    condition     = can(cidrnetmask(var.cidr)) && can(cidrsubnet(var.cidr, 4, 15))
    error_message = "Invalid cidr; review documented scope, pins and safety limits."
  }
}
variable "availability_zones" {
  description = "availability zones; see the module reference for restrictions."
  type        = list(string)
  validation {
    condition     = length(var.availability_zones) >= 2 && length(var.availability_zones) <= 3 && length(distinct(var.availability_zones)) == length(var.availability_zones)
    error_message = "Invalid availability_zones; review documented scope, pins and safety limits."
  }
}
variable "nat_mode" {
  description = "nat mode; see the module reference for restrictions."
  type        = string
  default     = "single"
  validation {
    condition     = contains(["none", "single", "per_az"], var.nat_mode) && (var.nat_mode != "none" || var.enable_endpoints)
    error_message = "Invalid nat_mode; review documented scope, pins and safety limits."
  }
}
variable "enable_endpoints" {
  description = "enable endpoints; see the module reference for restrictions."
  type        = bool
  default     = false
}
variable "retention_days" {
  description = "retention days; see the module reference for restrictions."
  type        = number
  default     = 30
  validation {
    condition     = contains([7, 14, 30, 60, 90, 120, 180, 365], var.retention_days)
    error_message = "Invalid retention_days; review documented scope, pins and safety limits."
  }
}
variable "retain_images" {
  description = "retain images; see the module reference for restrictions."
  type        = number
  default     = 30
}
variable "kubernetes_version" {
  description = "kubernetes version; see the module reference for restrictions."
  type        = string
  validation {
    condition     = can(regex("^1\\.[0-9]{2}$", var.kubernetes_version))
    error_message = "Invalid kubernetes_version; review documented scope, pins and safety limits."
  }
}
variable "node_ami_release" {
  description = "node ami release; see the module reference for restrictions."
  type        = string
  validation {
    condition     = can(regex("^[0-9]+\\.[0-9]+\\.[0-9]+-[0-9]{8}$", var.node_ami_release))
    error_message = "Invalid node_ami_release; review documented scope, pins and safety limits."
  }
}
variable "instance_types" {
  description = "instance types; see the module reference for restrictions."
  type        = list(string)
  default     = ["t3.large"]
  validation {
    condition     = length(var.instance_types) >= 1 && alltrue([for t in var.instance_types : can(regex("^(t3|m6i|m7i|c6i|c7i)\\.", t))])
    error_message = "Invalid instance_types; review documented scope, pins and safety limits."
  }
}
variable "capacity_type" {
  description = "capacity type; see the module reference for restrictions."
  type        = string
  default     = "ON_DEMAND"
  validation {
    condition     = contains(["ON_DEMAND", "SPOT"], var.capacity_type)
    error_message = "Invalid capacity_type; review documented scope, pins and safety limits."
  }
}
variable "min_nodes" {
  description = "min nodes; see the module reference for restrictions."
  type        = number
  default     = 1
  validation {
    condition     = var.min_nodes >= 1 && var.min_nodes == floor(var.min_nodes)
    error_message = "Invalid min_nodes; review documented scope, pins and safety limits."
  }
}
variable "max_nodes" {
  description = "max nodes; see the module reference for restrictions."
  type        = number
  default     = 3
  validation {
    condition     = var.max_nodes <= 10 && var.max_nodes >= var.min_nodes && var.max_nodes == floor(var.max_nodes)
    error_message = "Invalid max_nodes; review documented scope, pins and safety limits."
  }
}
variable "desired_nodes" {
  description = "desired nodes; see the module reference for restrictions."
  type        = number
  default     = 1
  validation {
    condition     = var.desired_nodes >= var.min_nodes && var.desired_nodes <= var.max_nodes && var.desired_nodes == floor(var.desired_nodes)
    error_message = "Invalid desired_nodes; review documented scope, pins and safety limits."
  }
}
variable "public_access_cidrs" {
  description = "public access cidrs; see the module reference for restrictions."
  type        = list(string)
  default     = []
  validation {
    condition     = alltrue([for cidr in var.public_access_cidrs : can(cidrnetmask(cidr)) && try(tonumber(split("/", cidr)[1]) >= 24, false)])
    error_message = "Invalid public_access_cidrs; review documented scope, pins and safety limits."
  }
}
variable "addons" {
  description = "addons; see the module reference for restrictions."
  type        = map(string)
  validation {
    condition     = toset(keys(var.addons)) == toset(["vpc-cni", "kube-proxy", "coredns", "eks-pod-identity-agent"]) && alltrue([for v in values(var.addons) : can(regex("^v[0-9]+\\.[0-9]+\\.[0-9]+-eksbuild\\.[0-9]+$", v))])
    error_message = "Invalid addons; review documented scope, pins and safety limits."
  }
}
variable "autoscaling_service_linked_role_arn" {
  description = "autoscaling service linked role arn; see the module reference for restrictions."
  type        = string
  validation {
    condition     = can(regex("^arn:aws:iam::[0-9]{12}:role/aws-service-role/autoscaling.amazonaws.com/AWSServiceRoleForAutoScaling", var.autoscaling_service_linked_role_arn))
    error_message = "Invalid autoscaling_service_linked_role_arn; review documented scope, pins and safety limits."
  }
}
variable "view_principal_arns" {
  description = "view principal arns; see the module reference for restrictions."
  type        = set(string)
  default     = []
  validation {
    condition     = alltrue([for arn in var.view_principal_arns : can(regex("^arn:aws:iam::[0-9]{12}:role/", arn))])
    error_message = "Invalid view_principal_arns; review documented scope, pins and safety limits."
  }
}
variable "deploy_principal_arns" {
  description = "deploy principal arns; see the module reference for restrictions."
  type        = set(string)
  default     = []
  validation {
    condition     = alltrue([for arn in var.deploy_principal_arns : can(regex("^arn:aws:iam::[0-9]{12}:role/", arn))]) && length(setintersection(var.view_principal_arns, var.deploy_principal_arns)) == 0
    error_message = "Invalid deploy_principal_arns; review documented scope, pins and safety limits."
  }
}
variable "enable_github_role" {
  description = "enable github role; see the module reference for restrictions."
  type        = bool
  default     = false
  validation {
    condition     = !var.enable_github_role || can(regex("^arn:aws:iam::[0-9]{12}:oidc-provider/token.actions.githubusercontent.com$", var.github_oidc_provider_arn))
    error_message = "Invalid enable_github_role; review documented scope, pins and safety limits."
  }
}
variable "github_oidc_provider_arn" {
  description = "github oidc provider arn; see the module reference for restrictions."
  type        = string
  default     = ""
}
variable "github_repository" {
  description = "github repository; see the module reference for restrictions."
  type        = string
  default     = "manikantbindass/KubeSentinel-AI"
  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "Invalid github_repository; review documented scope, pins and safety limits."
  }
}
variable "github_branch" {
  description = "github branch; see the module reference for restrictions."
  type        = string
  default     = "main"
  validation {
    condition     = can(regex("^[A-Za-z0-9_./-]+$", var.github_branch)) && !strcontains(var.github_branch, "*")
    error_message = "Invalid github_branch; review documented scope, pins and safety limits."
  }
}
variable "enable_workload_logs_identity" {
  description = "enable workload logs identity; see the module reference for restrictions."
  type        = bool
  default     = false
}
variable "enable_dns" {
  description = "enable dns; see the module reference for restrictions."
  type        = bool
  default     = false
  validation {
    condition     = !var.enable_dns || (var.dns_zone_id != "" && var.dns_record_name != "" && startswith(var.internal_load_balancer_dns_name, "internal-") && endswith(var.internal_load_balancer_dns_name, ".elb.amazonaws.com"))
    error_message = "Invalid enable_dns; review documented scope, pins and safety limits."
  }
}
variable "dns_zone_id" {
  description = "dns zone id; see the module reference for restrictions."
  type        = string
  default     = ""
}
variable "dns_record_name" {
  description = "dns record name; see the module reference for restrictions."
  type        = string
  default     = ""
}
variable "internal_load_balancer_dns_name" {
  description = "internal load balancer dns name; see the module reference for restrictions."
  type        = string
  default     = ""
}
