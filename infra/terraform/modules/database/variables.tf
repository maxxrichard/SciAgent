variable "identifier" {
  description = "RDS instance identifier and name prefix (e.g. sciagent-dev)."
  type        = string
}

variable "vpc_id" {
  description = "VPC to place the database security group in."
  type        = string
}

variable "subnet_ids" {
  description = "Private subnet IDs for the DB subnet group (at least two AZs)."
  type        = list(string)
}

variable "allowed_security_groups" {
  description = "Security groups allowed to connect on 5432, keyed by a static label (e.g. { eks = sg-... })."
  type        = map(string)
}

variable "engine_version" {
  description = "PostgreSQL engine version (major 16)."
  type        = string
  default     = "16"

  validation {
    condition     = startswith(var.engine_version, "16")
    error_message = "This module targets PostgreSQL 16 (parameter group family postgres16)."
  }
}

variable "instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t4g.medium"
}

variable "database_name" {
  description = "Initial database name."
  type        = string
  default     = "sciagent"
}

variable "master_username" {
  description = "Master user name. The password is managed by RDS in Secrets Manager."
  type        = string
  default     = "sciagent_admin"
}

variable "allocated_storage_gb" {
  description = "Initial storage in GiB."
  type        = number
  default     = 50
}

variable "max_allocated_storage_gb" {
  description = "Storage autoscaling ceiling in GiB."
  type        = number
  default     = 200
}

variable "multi_az" {
  description = "Deploy a synchronous standby in a second AZ."
  type        = bool
  default     = true
}

variable "backup_retention_days" {
  description = "Automated backup retention."
  type        = number
  default     = 7
}

variable "deletion_protection" {
  description = "Protect the instance from deletion and take a final snapshot on destroy."
  type        = bool
  default     = true
}

variable "apply_immediately" {
  description = "Apply modifications immediately instead of in the maintenance window."
  type        = bool
  default     = false
}

variable "performance_insights_retention_days" {
  description = "Performance Insights retention (7 is free tier; 31+ multiples for long-term)."
  type        = number
  default     = 7
}

variable "log_min_duration_statement_ms" {
  description = "Log statements slower than this (ms). -1 disables."
  type        = number
  default     = 1000
}

variable "maintenance_work_mem_kb" {
  description = "maintenance_work_mem in kB (vector index builds)."
  type        = number
  default     = 1048576
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
