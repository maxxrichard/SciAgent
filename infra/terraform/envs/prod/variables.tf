variable "project" {
  description = "Project name, used as the resource name prefix."
  type        = string
  default     = "sciagent"
}

variable "environment" {
  description = "Environment name."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging or prod."
  }
}

variable "region" {
  description = "AWS region."
  type        = string
  default     = "eu-central-1"
}

variable "allowed_account_ids" {
  description = "Guard rail: the provider refuses to run against any other AWS account."
  type        = list(string)
}

variable "app_namespace" {
  description = "Kubernetes namespace of the SciAgent Helm release."
  type        = string
  default     = "sciagent"
}

variable "airflow_namespace" {
  description = "Kubernetes namespace of the Airflow release."
  type        = string
  default     = "airflow"
}

# --- Network -----------------------------------------------------------------

variable "vpc_cidr" {
  description = "VPC CIDR (/16)."
  type        = string
}

variable "az_count" {
  description = "Number of AZs."
  type        = number
  default     = 3
}

variable "single_nat_gateway" {
  description = "Share one NAT gateway across AZs (dev only)."
  type        = bool
  default     = false
}

variable "interface_endpoints" {
  description = "Interface VPC endpoints to create."
  type        = list(string)
  default     = []
}

# --- EKS ---------------------------------------------------------------------

variable "kubernetes_version" {
  description = "EKS Kubernetes version."
  type        = string
  default     = "1.33"
}

variable "eks_endpoint_public_access" {
  description = "Expose the EKS API publicly (CIDR-restricted)."
  type        = bool
  default     = true
}

variable "eks_endpoint_public_access_cidrs" {
  description = "CIDRs allowed to reach the public EKS API endpoint."
  type        = list(string)
}

variable "eks_admin_role_arns" {
  description = "IAM roles granted cluster-admin via EKS access entries."
  type        = list(string)
  default     = []
}

variable "system_nodes" {
  description = "Sizing of the system node group (m6i.large)."
  type = object({
    min     = number
    max     = number
    desired = number
  })
}

variable "cpu_worker_nodes" {
  description = "Sizing of the autoscaling cpu-workers node group (m6i.2xlarge)."
  type = object({
    min     = number
    max     = number
    desired = number
  })
}

variable "cpu_workers_capacity_type" {
  description = "ON_DEMAND or SPOT for cpu-workers."
  type        = string
  default     = "ON_DEMAND"

  validation {
    condition     = contains(["ON_DEMAND", "SPOT"], var.cpu_workers_capacity_type)
    error_message = "cpu_workers_capacity_type must be ON_DEMAND or SPOT."
  }
}

variable "gpu_instance_type" {
  description = "Instance type of the gpu-inference node group."
  type        = string
  default     = "g5.2xlarge"
}

variable "gpu_nodes" {
  description = "Sizing of the gpu-inference node group (min is always 0 so it can scale to zero)."
  type = object({
    max     = number
    desired = number
  })
}

# --- Data / database ---------------------------------------------------------

variable "data_lake_force_destroy" {
  description = "Allow destroying non-empty data-lake buckets."
  type        = bool
  default     = false
}

variable "db_instance_class" {
  description = "RDS instance class."
  type        = string
}

variable "db_allocated_storage_gb" {
  description = "Initial RDS storage (GiB)."
  type        = number
}

variable "db_max_allocated_storage_gb" {
  description = "RDS storage autoscaling ceiling (GiB)."
  type        = number
}

variable "db_multi_az" {
  description = "Multi-AZ RDS deployment."
  type        = bool
}

variable "db_backup_retention_days" {
  description = "RDS automated backup retention."
  type        = number
}

variable "db_deletion_protection" {
  description = "RDS deletion protection (+ final snapshot)."
  type        = bool
}

variable "db_performance_insights_retention_days" {
  description = "Performance Insights retention."
  type        = number
  default     = 7
}

# --- Observability -----------------------------------------------------------

variable "log_retention_days" {
  description = "CloudWatch log retention."
  type        = number
}

variable "enable_amp" {
  description = "Create an Amazon Managed Prometheus workspace."
  type        = bool
  default     = false
}
