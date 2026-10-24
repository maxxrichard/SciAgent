output "endpoint" {
  description = "Writer endpoint host:port."
  value       = aws_db_instance.this.endpoint
}

output "address" {
  description = "Writer endpoint hostname."
  value       = aws_db_instance.this.address
}

output "port" {
  description = "PostgreSQL port."
  value       = aws_db_instance.this.port
}

output "database_name" {
  description = "Initial database name."
  value       = aws_db_instance.this.db_name
}

output "master_user_secret_arn" {
  description = "Secrets Manager ARN holding the RDS-managed master credentials (JSON: username, password)."
  value       = aws_db_instance.this.master_user_secret[0].secret_arn
}

output "kms_key_arn" {
  description = "KMS key encrypting storage, Performance Insights and the credentials secret."
  value       = aws_kms_key.db.arn
}

output "security_group_id" {
  description = "Database security group ID."
  value       = aws_security_group.db.id
}

output "post_provision_sql" {
  description = "One-time SQL to run after provisioning (pgvector needs no preload on RDS PostgreSQL 16)."
  value       = "CREATE EXTENSION IF NOT EXISTS vector;"
}
