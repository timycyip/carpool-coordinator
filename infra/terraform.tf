terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote backend with state locking (S3 + DynamoDB).
  # Bucket and lock table are bootstrapped once via:
  #   aws s3api create-bucket --bucket carpool-dev-terraform-state --region us-east-2 --create-bucket-configuration LocationConstraint=us-east-2
  #   aws s3api put-bucket-encryption --bucket carpool-dev-terraform-state --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"aws:kms"}}]}'
  #   aws dynamodb create-table --table-name carpool-dev-terraform-lock \
  #     --attribute-definitions AttributeName=LockID,AttributeType=S \
  #     --key-schema AttributeName=LockID,KeyType=HASH \
  #     --billing-mode PAY_PER_REQUEST --region us-east-2
  backend "s3" {
    bucket         = "carpool-dev-terraform-state"
    key            = "infra/terraform.tfstate"
    region         = "us-east-2"
    dynamodb_table = "carpool-dev-terraform-lock"
    encrypt        = true
  }
}

provider "aws" {
  region = var.region
}
