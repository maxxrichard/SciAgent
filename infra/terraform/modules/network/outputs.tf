output "vpc_id" {
  description = "ID of the VPC."
  value       = aws_vpc.this.id
}

output "vpc_cidr" {
  description = "CIDR block of the VPC."
  value       = aws_vpc.this.cidr_block
}

output "azs" {
  description = "Availability zones used."
  value       = local.azs
}

output "private_subnet_ids" {
  description = "Private subnet IDs (EKS nodes, RDS)."
  value       = aws_subnet.private[*].id
}

output "public_subnet_ids" {
  description = "Public subnet IDs (internet-facing ALBs, NAT)."
  value       = aws_subnet.public[*].id
}

output "private_route_table_ids" {
  description = "Private route table IDs."
  value       = aws_route_table.private[*].id
}

output "s3_vpc_endpoint_id" {
  description = "ID of the S3 gateway endpoint (used in bucket policies to pin access to the VPC)."
  value       = aws_vpc_endpoint.s3.id
}

output "nat_public_ips" {
  description = "Elastic IPs of the NAT gateways (allow-list these at external data providers)."
  value       = aws_eip.nat[*].public_ip
}
