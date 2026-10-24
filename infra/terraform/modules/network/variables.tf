variable "name" {
  description = "Name prefix for all network resources (e.g. sciagent-dev)."
  type        = string
}

variable "cluster_name" {
  description = "EKS cluster name, used for the kubernetes.io/cluster subnet discovery tag."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block of the VPC. Must be a /16 for the default subnet math."
  type        = string
  default     = "10.0.0.0/16"

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr)) && endswith(var.vpc_cidr, "/16")
    error_message = "vpc_cidr must be a valid /16 CIDR block."
  }
}

variable "az_count" {
  description = "Number of availability zones to span."
  type        = number
  default     = 3

  validation {
    condition     = var.az_count >= 2 && var.az_count <= 3
    error_message = "az_count must be 2 or 3 (EKS requires at least two AZs)."
  }
}

variable "single_nat_gateway" {
  description = "Use one shared NAT gateway (cheaper, not AZ-resilient). Recommended for dev only."
  type        = bool
  default     = false
}

variable "interface_endpoints" {
  description = "AWS service short names to create interface VPC endpoints for (e.g. ecr.api, ecr.dkr, sts, logs)."
  type        = list(string)
  default     = []
}

variable "enable_flow_logs" {
  description = "Ship rejected-traffic VPC flow logs to CloudWatch."
  type        = bool
  default     = false
}

variable "flow_logs_log_group_arn" {
  description = "CloudWatch log group ARN for VPC flow logs. Required when enable_flow_logs is true."
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
