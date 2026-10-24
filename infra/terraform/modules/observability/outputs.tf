output "logs_kms_key_arn" {
  description = "KMS key ARN for CloudWatch log groups."
  value       = aws_kms_key.logs.arn
}

output "log_group_names" {
  description = "Component -> CloudWatch log group name."
  value       = { for k, g in aws_cloudwatch_log_group.component : k => g.name }
}

output "vpc_flow_logs_log_group_arn" {
  description = "Log group ARN for VPC flow logs."
  value       = aws_cloudwatch_log_group.vpc_flow_logs.arn
}

output "fluent_bit_role_arn" {
  description = "IRSA role ARN for the Fluent Bit service account."
  value       = aws_iam_role.fluent_bit.arn
}

output "amp_workspace_id" {
  description = "AMP workspace ID (null when disabled)."
  value       = try(aws_prometheus_workspace.this[0].id, null)
}

output "amp_remote_write_url" {
  description = "AMP remote-write endpoint (null when disabled)."
  value       = try("${aws_prometheus_workspace.this[0].prometheus_endpoint}api/v1/remote_write", null)
}

output "amp_remote_write_role_arn" {
  description = "IRSA role ARN for Prometheus remote-write (null when disabled)."
  value       = try(aws_iam_role.amp_remote_write[0].arn, null)
}
