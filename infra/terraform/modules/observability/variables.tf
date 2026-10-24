variable "name_prefix" {
  description = "Name prefix (e.g. sciagent-dev)."
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod); used in log group paths."
  type        = string
}

variable "log_components" {
  description = "Components that get a dedicated log group /sciagent/<env>/<component>."
  type        = list(string)
  default     = ["api", "mcp-imaging", "mcp-genomics", "mcp-clinical", "vllm", "airflow", "audit"]
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days."
  type        = number
  default     = 30

  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653], var.log_retention_days)
    error_message = "log_retention_days must be a value accepted by CloudWatch Logs."
  }
}

variable "oidc_provider_arn" {
  description = "EKS IAM OIDC provider ARN."
  type        = string
}

variable "oidc_provider_url" {
  description = "OIDC issuer without https://."
  type        = string
}

variable "fluent_bit_namespace" {
  description = "Namespace of the Fluent Bit DaemonSet."
  type        = string
  default     = "amazon-cloudwatch"
}

variable "fluent_bit_service_account" {
  description = "Service account of the Fluent Bit DaemonSet."
  type        = string
  default     = "fluent-bit"
}

variable "enable_amp" {
  description = "Create an Amazon Managed Service for Prometheus workspace and a remote-write IRSA role."
  type        = bool
  default     = false
}

variable "prometheus_namespace" {
  description = "Namespace of the in-cluster Prometheus that remote-writes to AMP."
  type        = string
  default     = "monitoring"
}

variable "prometheus_service_account" {
  description = "Service account of the in-cluster Prometheus."
  type        = string
  default     = "kube-prometheus-stack-prometheus"
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
