output "bucket_names" {
  description = "Zone -> bucket name."
  value       = { for k, b in aws_s3_bucket.zone : k => b.id }
}

output "bucket_arns" {
  description = "Zone -> bucket ARN."
  value       = { for k, b in aws_s3_bucket.zone : k => b.arn }
}

output "bucket_uris" {
  description = "Zone -> s3:// URI (feeds SCIAGENT_DATA_LAKE_URI)."
  value       = { for k, b in aws_s3_bucket.zone : k => "s3://${b.id}" }
}

output "kms_key_arn" {
  description = "ARN of the data-lake KMS key. Consumers need kms:Decrypt / kms:GenerateDataKey on it."
  value       = aws_kms_key.data_lake.arn
}

output "access_logs_bucket" {
  description = "Bucket receiving S3 server access logs."
  value       = aws_s3_bucket.logs.id
}
