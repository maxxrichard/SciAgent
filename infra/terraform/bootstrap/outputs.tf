output "state_bucket" {
  description = "Terraform state bucket."
  value       = aws_s3_bucket.state.id
}

output "lock_table" {
  description = "Terraform state lock table."
  value       = aws_dynamodb_table.lock.name
}

output "github_plan_role_arn" {
  description = "Store as the AWS_PLAN_ROLE_ARN_<ENV> GitHub secret."
  value       = aws_iam_role.github_plan.arn
}

output "github_apply_role_arn" {
  description = "Store as the AWS_APPLY_ROLE_ARN_<ENV> GitHub environment secret."
  value       = aws_iam_role.github_apply.arn
}
