/**
 * observability: KMS-encrypted CloudWatch log groups for SciAgent workloads,
 * an IRSA role for the Fluent Bit log shipper, and an optional Amazon Managed
 * Service for Prometheus (AMP) workspace with a remote-write IRSA role.
 */

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}
data "aws_region" "current" {}

locals {
  tags       = merge(var.tags, { Module = "observability" })
  account_id = data.aws_caller_identity.current.account_id
  partition  = data.aws_partition.current.partition
  region     = data.aws_region.current.name

  log_groups = {
    for c in var.log_components : c => "/sciagent/${var.environment}/${c}"
  }
}

data "aws_iam_policy_document" "logs_kms" {
  statement {
    sid       = "EnableRootAccount"
    effect    = "Allow"
    actions   = ["kms:*"]
    resources = ["*"]

    principals {
      type        = "AWS"
      identifiers = ["arn:${local.partition}:iam::${local.account_id}:root"]
    }
  }

  # CloudWatch Logs encrypts log groups in this account/region with the key.
  statement {
    sid    = "AllowCloudWatchLogs"
    effect = "Allow"
    actions = [
      "kms:Encrypt*",
      "kms:Decrypt*",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:Describe*",
    ]
    resources = ["*"]

    principals {
      type        = "Service"
      identifiers = ["logs.${local.region}.amazonaws.com"]
    }

    condition {
      test     = "ArnLike"
      variable = "kms:EncryptionContext:aws:logs:arn"
      values   = ["arn:${local.partition}:logs:${local.region}:${local.account_id}:log-group:*"]
    }
  }
}

resource "aws_kms_key" "logs" {
  description             = "${var.name_prefix} CloudWatch Logs encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  policy                  = data.aws_iam_policy_document.logs_kms.json
  tags                    = local.tags
}

resource "aws_kms_alias" "logs" {
  name          = "alias/${var.name_prefix}-logs"
  target_key_id = aws_kms_key.logs.key_id
}

resource "aws_cloudwatch_log_group" "component" {
  for_each = local.log_groups

  name              = each.value
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.logs.arn
  tags              = merge(local.tags, { Component = each.key })
}

resource "aws_cloudwatch_log_group" "vpc_flow_logs" {
  name              = "/sciagent/${var.environment}/vpc-flow-logs"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.logs.arn
  tags              = merge(local.tags, { Component = "vpc-flow-logs" })
}

# --- Fluent Bit (aws-for-fluent-bit) IRSA role -------------------------------

data "aws_iam_policy_document" "fluent_bit_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:sub"
      values   = ["system:serviceaccount:${var.fluent_bit_namespace}:${var.fluent_bit_service_account}"]
    }

    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "fluent_bit" {
  name               = "${var.name_prefix}-fluent-bit"
  assume_role_policy = data.aws_iam_policy_document.fluent_bit_assume.json
  tags               = local.tags
}

data "aws_iam_policy_document" "fluent_bit" {
  statement {
    sid       = "WriteSciAgentLogs"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"]
    resources = [for g in aws_cloudwatch_log_group.component : "${g.arn}:*"]
  }

  statement {
    sid       = "DescribeLogGroups"
    effect    = "Allow"
    actions   = ["logs:DescribeLogGroups"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "fluent_bit" {
  name   = "cloudwatch-logs-write"
  role   = aws_iam_role.fluent_bit.id
  policy = data.aws_iam_policy_document.fluent_bit.json
}

# --- Optional: Amazon Managed Service for Prometheus -------------------------

resource "aws_prometheus_workspace" "this" {
  count = var.enable_amp ? 1 : 0

  alias = "${var.name_prefix}-metrics"

  logging_configuration {
    log_group_arn = "${aws_cloudwatch_log_group.amp[0].arn}:*"
  }

  tags = local.tags
}

resource "aws_cloudwatch_log_group" "amp" {
  count = var.enable_amp ? 1 : 0

  name              = "/sciagent/${var.environment}/amp"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.logs.arn
  tags              = local.tags
}

data "aws_iam_policy_document" "amp_assume" {
  count = var.enable_amp ? 1 : 0

  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:sub"
      values   = ["system:serviceaccount:${var.prometheus_namespace}:${var.prometheus_service_account}"]
    }

    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "amp_remote_write" {
  count = var.enable_amp ? 1 : 0

  name               = "${var.name_prefix}-amp-remote-write"
  assume_role_policy = data.aws_iam_policy_document.amp_assume[0].json
  tags               = local.tags
}

resource "aws_iam_role_policy" "amp_remote_write" {
  count = var.enable_amp ? 1 : 0

  name = "amp-remote-write"
  role = aws_iam_role.amp_remote_write[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["aps:RemoteWrite", "aps:QueryMetrics", "aps:GetSeries", "aps:GetLabels", "aps:GetMetricMetadata"]
      Resource = aws_prometheus_workspace.this[0].arn
    }]
  })
}
