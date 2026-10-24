/**
 * eks: EKS control plane, managed node groups (system / cpu-workers /
 * gpu-inference), the IAM OIDC provider for IRSA, and core add-ons.
 */

data "aws_partition" "current" {}

locals {
  partition = data.aws_partition.current.partition
  tags      = merge(var.tags, { Module = "eks" })

  # Map Kubernetes taint effects to the EKS API enum.
  taint_effects = {
    NoSchedule       = "NO_SCHEDULE"
    NoExecute        = "NO_EXECUTE"
    PreferNoSchedule = "PREFER_NO_SCHEDULE"
  }

  # Cluster-autoscaler can only scale a node group up from zero if the ASG
  # advertises the labels/taints/resources its nodes will have.
  autoscaler_template_tags = merge([
    for ng_name, ng in var.node_groups : merge(
      {
        for k, v in ng.labels :
        "${ng_name}|k8s.io/cluster-autoscaler/node-template/label/${k}" => { node_group = ng_name, key = "k8s.io/cluster-autoscaler/node-template/label/${k}", value = v }
      },
      {
        for t in ng.taints :
        "${ng_name}|k8s.io/cluster-autoscaler/node-template/taint/${t.key}" => { node_group = ng_name, key = "k8s.io/cluster-autoscaler/node-template/taint/${t.key}", value = "${t.value}:${t.effect}" }
      },
      ng.gpu_count > 0 ? {
        "${ng_name}|k8s.io/cluster-autoscaler/node-template/resources/nvidia.com/gpu" = { node_group = ng_name, key = "k8s.io/cluster-autoscaler/node-template/resources/nvidia.com/gpu", value = tostring(ng.gpu_count) }
      } : {}
    )
  ]...)
}

# --- KMS: envelope encryption for Kubernetes Secrets -------------------------

resource "aws_kms_key" "eks" {
  description             = "${var.cluster_name} EKS secrets envelope encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  tags                    = local.tags
}

resource "aws_kms_alias" "eks" {
  name          = "alias/${var.cluster_name}-eks"
  target_key_id = aws_kms_key.eks.key_id
}

# --- Control plane -----------------------------------------------------------

resource "aws_iam_role" "cluster" {
  name = "${var.cluster_name}-cluster"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "eks.amazonaws.com" }
      Action    = ["sts:AssumeRole", "sts:TagSession"]
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "cluster" {
  for_each = toset([
    "AmazonEKSClusterPolicy",
    "AmazonEKSVPCResourceController",
  ])

  role       = aws_iam_role.cluster.name
  policy_arn = "arn:${local.partition}:iam::aws:policy/${each.value}"
}

resource "aws_cloudwatch_log_group" "cluster" {
  # EKS writes control-plane logs to this exact name; creating it ourselves
  # lets us set retention and KMS.
  name              = "/aws/eks/${var.cluster_name}/cluster"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.logs_kms_key_arn
  tags              = local.tags
}

resource "aws_eks_cluster" "this" {
  name     = var.cluster_name
  version  = var.kubernetes_version
  role_arn = aws_iam_role.cluster.arn

  enabled_cluster_log_types = ["api", "audit", "authenticator", "controllerManager", "scheduler"]

  vpc_config {
    subnet_ids              = var.private_subnet_ids
    endpoint_private_access = true
    endpoint_public_access  = var.endpoint_public_access
    public_access_cidrs     = var.endpoint_public_access ? var.endpoint_public_access_cidrs : null
  }

  access_config {
    authentication_mode                         = "API"
    bootstrap_cluster_creator_admin_permissions = true
  }

  encryption_config {
    resources = ["secrets"]
    provider {
      key_arn = aws_kms_key.eks.arn
    }
  }

  tags = local.tags

  depends_on = [
    aws_iam_role_policy_attachment.cluster,
    aws_cloudwatch_log_group.cluster,
  ]
}

# --- IRSA: IAM OIDC provider -------------------------------------------------

data "tls_certificate" "oidc" {
  url = aws_eks_cluster.this.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "this" {
  url             = aws_eks_cluster.this.identity[0].oidc[0].issuer
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.oidc.certificates[0].sha1_fingerprint]
  tags            = local.tags
}

# --- Cluster admins (EKS access entries) ------------------------------------

resource "aws_eks_access_entry" "admin" {
  for_each = toset(var.admin_role_arns)

  cluster_name  = aws_eks_cluster.this.name
  principal_arn = each.value
  type          = "STANDARD"
  tags          = local.tags
}

resource "aws_eks_access_policy_association" "admin" {
  for_each = toset(var.admin_role_arns)

  cluster_name  = aws_eks_cluster.this.name
  principal_arn = each.value
  policy_arn    = "arn:${local.partition}:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }

  depends_on = [aws_eks_access_entry.admin]
}

# --- Managed node groups -----------------------------------------------------

resource "aws_iam_role" "node" {
  name = "${var.cluster_name}-node"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "node" {
  for_each = toset([
    "AmazonEKSWorkerNodePolicy",
    "AmazonEKS_CNI_Policy",
    "AmazonEC2ContainerRegistryReadOnly",
    "AmazonSSMManagedInstanceCore",
  ])

  role       = aws_iam_role.node.name
  policy_arn = "arn:${local.partition}:iam::aws:policy/${each.value}"
}

resource "aws_launch_template" "node" {
  for_each = var.node_groups

  name_prefix            = "${var.cluster_name}-${each.key}-"
  update_default_version = true

  # IMDSv2 only, hop limit 1: pods cannot reach node credentials and must use IRSA.
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size           = each.value.disk_size_gb
      volume_type           = "gp3"
      encrypted             = true
      delete_on_termination = true
    }
  }

  tag_specifications {
    resource_type = "instance"
    tags          = merge(local.tags, { Name = "${var.cluster_name}-${each.key}" })
  }

  tag_specifications {
    resource_type = "volume"
    tags          = merge(local.tags, { Name = "${var.cluster_name}-${each.key}" })
  }

  tags = local.tags
}

resource "aws_eks_node_group" "this" {
  for_each = var.node_groups

  cluster_name    = aws_eks_cluster.this.name
  node_group_name = each.key
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.private_subnet_ids
  version         = var.kubernetes_version

  ami_type       = each.value.ami_type
  capacity_type  = each.value.capacity_type
  instance_types = each.value.instance_types

  scaling_config {
    min_size     = each.value.min_size
    max_size     = each.value.max_size
    desired_size = each.value.desired_size
  }

  update_config {
    max_unavailable_percentage = 33
  }

  launch_template {
    id      = aws_launch_template.node[each.key].id
    version = aws_launch_template.node[each.key].latest_version
  }

  labels = merge(each.value.labels, { "sciagent.io/node-group" = each.key })

  dynamic "taint" {
    for_each = each.value.taints
    content {
      key    = taint.value.key
      value  = taint.value.value
      effect = local.taint_effects[taint.value.effect]
    }
  }

  tags = merge(local.tags, {
    "k8s.io/cluster-autoscaler/enabled"             = tostring(each.value.autoscaling)
    "k8s.io/cluster-autoscaler/${var.cluster_name}" = "owned"
  })

  # desired_size is owned by cluster-autoscaler after creation.
  lifecycle {
    ignore_changes = [scaling_config[0].desired_size]
  }

  depends_on = [aws_iam_role_policy_attachment.node]
}

# Node group tags are not propagated to the underlying ASG; tag it directly.
resource "aws_autoscaling_group_tag" "autoscaler_template" {
  for_each = local.autoscaler_template_tags

  autoscaling_group_name = aws_eks_node_group.this[each.value.node_group].resources[0].autoscaling_groups[0].name

  tag {
    key                 = each.value.key
    value               = each.value.value
    propagate_at_launch = false
  }
}

# --- Add-ons -----------------------------------------------------------------

data "aws_iam_policy_document" "ebs_csi_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.this.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${replace(aws_iam_openid_connect_provider.this.url, "https://", "")}:sub"
      values   = ["system:serviceaccount:kube-system:ebs-csi-controller-sa"]
    }

    condition {
      test     = "StringEquals"
      variable = "${replace(aws_iam_openid_connect_provider.this.url, "https://", "")}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ebs_csi" {
  name               = "${var.cluster_name}-ebs-csi"
  assume_role_policy = data.aws_iam_policy_document.ebs_csi_assume.json
  tags               = local.tags
}

resource "aws_iam_role_policy_attachment" "ebs_csi" {
  role       = aws_iam_role.ebs_csi.name
  policy_arn = "arn:${local.partition}:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
}

locals {
  addons = {
    "vpc-cni"                = { service_account_role_arn = null, needs_nodes = false }
    "kube-proxy"             = { service_account_role_arn = null, needs_nodes = false }
    "eks-pod-identity-agent" = { service_account_role_arn = null, needs_nodes = false }
    "coredns"                = { service_account_role_arn = null, needs_nodes = true }
    "aws-ebs-csi-driver"     = { service_account_role_arn = aws_iam_role.ebs_csi.arn, needs_nodes = true }
  }
}

# Add-ons that run as DaemonSets can be installed before nodes exist.
resource "aws_eks_addon" "pre_nodes" {
  for_each = { for k, v in local.addons : k => v if !v.needs_nodes }

  cluster_name                = aws_eks_cluster.this.name
  addon_name                  = each.key
  addon_version               = lookup(var.addon_versions, each.key, null)
  service_account_role_arn    = each.value.service_account_role_arn
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"
  tags                        = local.tags
}

# Add-ons with Deployments need schedulable nodes or they never go ACTIVE.
resource "aws_eks_addon" "post_nodes" {
  for_each = { for k, v in local.addons : k => v if v.needs_nodes }

  cluster_name                = aws_eks_cluster.this.name
  addon_name                  = each.key
  addon_version               = lookup(var.addon_versions, each.key, null)
  service_account_role_arn    = each.value.service_account_role_arn
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"
  tags                        = local.tags

  depends_on = [aws_eks_node_group.this]
}
