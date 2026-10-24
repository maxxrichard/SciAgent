variable "name_prefix" {
  description = "Bucket name prefix (e.g. sciagent-dev). The AWS account ID is appended for global uniqueness."
  type        = string
}

variable "zones" {
  description = "Data-lake zones and their lifecycle settings. Keys become bucket name segments."
  type = map(object({
    transition_ia_days           = number
    transition_glacier_days      = optional(number)
    transition_deep_archive_days = optional(number)
    noncurrent_expiration_days   = optional(number, 90)
  }))

  default = {
    raw = {
      transition_ia_days           = 30
      transition_glacier_days      = 90
      transition_deep_archive_days = 365
      noncurrent_expiration_days   = 180
    }
    curated = {
      transition_ia_days         = 90
      noncurrent_expiration_days = 90
    }
    artifacts = {
      transition_ia_days         = 30
      transition_glacier_days    = 180
      noncurrent_expiration_days = 60
    }
  }

  validation {
    condition     = alltrue([for z in ["raw", "curated", "artifacts"] : contains(keys(var.zones), z)])
    error_message = "zones must define at least raw, curated and artifacts."
  }

  validation {
    # S3 requires >= 30 days in STANDARD before STANDARD_IA.
    condition     = alltrue([for z in values(var.zones) : z.transition_ia_days >= 30])
    error_message = "transition_ia_days must be >= 30."
  }
}

variable "access_log_retention_days" {
  description = "Days to keep S3 server access logs."
  type        = number
  default     = 365
}

variable "force_destroy" {
  description = "Allow terraform destroy to delete non-empty buckets. Never enable in prod."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
