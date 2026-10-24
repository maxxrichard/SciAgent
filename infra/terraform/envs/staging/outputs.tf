output "cluster_name" {
  description = "EKS cluster name."
  value       = module.eks.cluster_name
}

output "kubeconfig_command" {
  description = "Configure kubectl for this cluster."
  value       = "aws eks update-kubeconfig --region ${var.region} --name ${module.eks.cluster_name}"
}

output "data_lake_buckets" {
  description = "Zone -> s3:// URI."
  value       = module.data_lake.bucket_uris
}

output "data_lake_uri" {
  description = "Value for SCIAGENT_DATA_LAKE_URI (curated zone, the zone agents read)."
  value       = module.data_lake.bucket_uris["curated"]
}

output "database_endpoint" {
  description = "RDS PostgreSQL endpoint."
  value       = module.database.endpoint
}

output "database_master_secret_arn" {
  description = "Secrets Manager ARN of the RDS-managed master credentials."
  value       = module.database.master_user_secret_arn
}

output "database_post_provision_sql" {
  description = "Run once against the database after the first apply."
  value       = module.database.post_provision_sql
}

output "irsa_role_arns" {
  description = "Workload -> IRSA role ARN (api, mcp, airflow)."
  value       = module.iam.role_arns
}

output "fluent_bit_role_arn" {
  description = "IRSA role ARN for Fluent Bit."
  value       = module.observability.fluent_bit_role_arn
}

output "amp_remote_write_url" {
  description = "AMP remote-write URL (null when AMP is disabled)."
  value       = module.observability.amp_remote_write_url
}

# Paste into deploy/helm/sciagent values-<env>.yaml.
output "helm_values" {
  description = "Infrastructure-derived Helm values for the sciagent chart."
  value = {
    "api.serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn" = module.iam.role_arns["api"]
    "mcp.serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn" = module.iam.role_arns["mcp"]
    "config.dataLakeUri"                                            = module.data_lake.bucket_uris["curated"]
  }
}
