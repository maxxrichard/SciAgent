output "role_arns" {
  description = "Workload -> IRSA role ARN (set as eks.amazonaws.com/role-arn on the service account)."
  value       = { for k, r in aws_iam_role.workload : k => r.arn }
}

output "role_names" {
  description = "Workload -> IAM role name."
  value       = { for k, r in aws_iam_role.workload : k => r.name }
}
