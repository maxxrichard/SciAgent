variable "cluster_name" {
  description = "Name of the EKS cluster."
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes minor version for the control plane and node groups."
  type        = string
  default     = "1.33"
}

variable "private_subnet_ids" {
  description = "Private subnets for the control plane ENIs and the node groups."
  type        = list(string)
}

variable "endpoint_public_access" {
  description = "Expose the Kubernetes API endpoint publicly (restricted by endpoint_public_access_cidrs)."
  type        = bool
  default     = true
}

variable "endpoint_public_access_cidrs" {
  description = "CIDRs allowed to reach the public API endpoint."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "admin_role_arns" {
  description = "IAM role ARNs granted cluster-admin through EKS access entries (e.g. SSO admin role, CI deploy role)."
  type        = list(string)
  default     = []
}

variable "node_groups" {
  description = "Managed node groups keyed by name."
  type = map(object({
    instance_types = list(string)
    ami_type       = optional(string, "AL2023_x86_64_STANDARD")
    capacity_type  = optional(string, "ON_DEMAND")
    min_size       = number
    max_size       = number
    desired_size   = number
    disk_size_gb   = optional(number, 50)
    autoscaling    = optional(bool, true)
    gpu_count      = optional(number, 0)
    labels         = optional(map(string), {})
    taints = optional(list(object({
      key    = string
      value  = string
      effect = string
    })), [])
  }))

  validation {
    condition = alltrue([
      for ng in values(var.node_groups) : ng.min_size <= ng.desired_size && ng.desired_size <= ng.max_size
    ])
    error_message = "Each node group must satisfy min_size <= desired_size <= max_size."
  }

  validation {
    condition = alltrue(flatten([
      for ng in values(var.node_groups) : [
        for t in ng.taints : contains(["NoSchedule", "NoExecute", "PreferNoSchedule"], t.effect)
      ]
    ]))
    error_message = "Taint effect must be one of NoSchedule, NoExecute, PreferNoSchedule."
  }
}

variable "addon_versions" {
  description = "Optional pinned add-on versions keyed by add-on name. Unset add-ons use the EKS default for the cluster version."
  type        = map(string)
  default     = {}
}

variable "log_retention_days" {
  description = "Retention for EKS control-plane logs."
  type        = number
  default     = 30
}

variable "logs_kms_key_arn" {
  description = "KMS key ARN used to encrypt the control-plane CloudWatch log group."
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
