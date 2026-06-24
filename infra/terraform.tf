terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote backend with state locking. Uncomment and populate after
  # bootstrapping the S3 bucket and DynamoDB lock table (see ADR-0003).
  #
  # backend "s3" {
  #   bucket         = "carpool-terraform-state"
  #   key            = "infra/terraform.tfstate"
  #   region         = "us-east-2"
  #   dynamodb_table = "carpool-terraform-locks"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.region
}
