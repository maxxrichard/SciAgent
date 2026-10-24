output "cluster_name" {
  description = "EKS cluster name."
  value       = aws_eks_cluster.this.name
}

output "cluster_arn" {
  description = "EKS cluster ARN."
  value       = aws_eks_cluster.this.arn
}

output "cluster_endpoint" {
  description = "Kubernetes API server endpoint."
  value       = aws_eks_cluster.this.endpoint
}

output "cluster_certificate_authority_data" {
  description = "Base64-encoded cluster CA certificate."
  value       = aws_eks_cluster.this.certificate_authority[0].data
}

output "cluster_security_group_id" {
  description = "EKS-managed cluster security group, attached to all managed nodes."
  value       = aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
}

output "oidc_provider_arn" {
  description = "ARN of the IAM OIDC provider (IRSA trust principal)."
  value       = aws_iam_openid_connect_provider.this.arn
}

output "oidc_provider_url" {
  description = "OIDC issuer host/path without the https:// scheme (IRSA condition key prefix)."
  value       = replace(aws_iam_openid_connect_provider.this.url, "https://", "")
}

output "node_role_arn" {
  description = "IAM role ARN of the managed node groups."
  value       = aws_iam_role.node.arn
}

output "node_groups" {
  description = "Node group name -> ASG name."
  value       = { for k, ng in aws_eks_node_group.this : k => ng.resources[0].autoscaling_groups[0].name }
}

output "kubeconfig_command" {
  description = "Command to write a kubeconfig entry for this cluster."
  value       = "aws eks update-kubeconfig --name ${aws_eks_cluster.this.name}"
}
