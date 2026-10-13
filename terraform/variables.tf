variable "aws_profile" {
  description = "AWS CLI profile used by the Terraform AWS providers."
  type        = string
  default     = "dr-lab"
}

variable "source_region" {
  description = "AWS region containing the source bucket and backup Lambda."
  type        = string
}

variable "destination_region" {
  description = "Different AWS region containing the recovery bucket."
  type        = string

  validation {
    condition     = var.destination_region != var.source_region
    error_message = "The recovery bucket must be in a different region from the source bucket."
  }
}

variable "name_prefix" {
  description = "Short lowercase prefix used in globally unique resource names."
  type        = string
  default     = "dr-lab"

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{1,28}[a-z0-9]$", var.name_prefix))
    error_message = "Use 3-30 lowercase letters, numbers, or hyphens; start and end with a letter or number."
  }
}

variable "alert_email" {
  description = "Email address for SNS backup failure alerts; confirm the subscription email after apply."
  type        = string

  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.alert_email))
    error_message = "Provide a valid email address for the SNS subscription."
  }
}

variable "backup_prefix" {
  description = "Destination key prefix containing immutable per-run recovery points."
  type        = string
  default     = "recovery"

  validation {
    condition     = length(trim(var.backup_prefix, "/")) > 0
    error_message = "The backup prefix must contain at least one non-slash character."
  }
}

variable "retention_days" {
  description = "Days to retain current and noncurrent recovery object versions."
  type        = number
  default     = 14

  validation {
    condition     = var.retention_days >= 1 && var.retention_days <= 3650
    error_message = "Retention must be between 1 and 3650 days."
  }
}

variable "schedule_expression" {
  description = "EventBridge schedule in UTC. The default runs once per day at 02:00 UTC."
  type        = string
  default     = "cron(0 2 * * ? *)"
}