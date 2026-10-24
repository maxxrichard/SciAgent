variable "name_prefix" {
  description = "IAM role name prefix (e.g. sciagent-dev)."
  type        = string
}

variable "oidc_provider_arn" {
  description = "ARN of the EKS IAM OIDC provider."
  type        = string
}

variable "oidc_provider_url" {
  description = "OIDC issuer without https:// (e.g. oidc.eks.eu-central-1.amazonaws.com/id/ABC...)."
  type        = string
}

variable "bucket_arns" {
  description = "Data-lake zone -> bucket ARN (from the data_lake module)."
  type        = map(string)
}

variable "kms_key_arn" {
  description = "Data-lake KMS key ARN."
  type        = string
}

variable "workloads" {
  description = <<-EOT
    IRSA workloads. Service account names must match the Helm chart
    (deploy/helm/sciagent values: <component>.serviceAccount.name) and the
    Airflow chart.
  EOT
  type = map(object({
    description      = string
    namespace        = string
    service_accounts = list(string)
    read_zones       = optional(list(string), [])
    write_zones      = optional(list(string), [])
    delete_zones     = optional(list(string), [])
  }))

  default = {
    # FastAPI gateway + agent orchestrator: reads harmonised data, persists run artefacts.
    api = {
      description      = "SciAgent API / agent orchestrator"
      namespace        = "sciagent"
      service_accounts = ["sciagent-api"]
      read_zones       = ["curated", "artifacts"]
      write_zones      = ["artifacts"]
    }
    # MCP tool servers (imaging, genomics, clinical) used by agents: read-only on curated.
    mcp = {
      description      = "SciAgent MCP tool servers (agent tool access)"
      namespace        = "sciagent"
      service_accounts = ["sciagent-mcp"]
      read_zones       = ["curated"]
    }
    # Ingestion / harmonisation pipelines.
    airflow = {
      description      = "Airflow ingestion and harmonisation pipelines"
      namespace        = "airflow"
      service_accounts = ["airflow-worker", "airflow-scheduler", "airflow-triggerer"]
      read_zones       = ["raw", "curated"]
      write_zones      = ["raw", "curated"]
      delete_zones     = ["curated"]
    }
  }

  validation {
    condition = alltrue(flatten([
      for w in values(var.workloads) : [
        for z in concat(w.read_zones, w.write_zones, w.delete_zones) : contains(["raw", "curated", "artifacts"], z)
      ]
    ]))
    error_message = "Zones must be one of raw, curated, artifacts."
  }
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
