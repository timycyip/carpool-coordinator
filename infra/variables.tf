variable "region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-2"
}

variable "environment" {
  description = "Non-production deployment environment (dev or staging)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging"], var.environment)
    error_message = "Only dev and staging environments are supported; production is intentionally blocked."
  }
}

variable "cost_alert_email" {
  description = "Email subscriber for the single account-wide monthly AWS budget; configure only in the dev GitHub Environment."
  type        = string
  default     = ""
  sensitive   = true
}

variable "monthly_cost_budget_usd" {
  description = "Account-wide monthly AWS cost alert threshold, managed by the dev Terraform state."
  type        = number
  default     = 5

  validation {
    condition     = var.monthly_cost_budget_usd > 0
    error_message = "The monthly AWS cost budget must be greater than zero."
  }
}
