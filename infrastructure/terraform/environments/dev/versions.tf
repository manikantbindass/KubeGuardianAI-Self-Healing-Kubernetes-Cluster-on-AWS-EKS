terraform {
  required_version = ">= 1.13.5, < 1.14.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 6.71.0"
    }
  }
  backend "s3" {}
}
