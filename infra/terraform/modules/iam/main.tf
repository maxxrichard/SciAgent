/**
 * iam: IRSA roles for SciAgent workloads with least-privilege data-lake access.
 *
 * Each workload maps one or more Kubernetes service accounts to an IAM role.
 * Access is expressed per data-lake zone:
 *   read_zones   -> ListBucket + GetObject(+Version)  + kms:Decrypt
 *   write_zones  -> PutObject + multipart housekeeping + kms:GenerateDataKey
 *   delete_zones -> DeleteObject (current version only; versions are retained)
 * KMS use is restricted to calls made through S3 in this region.
 */

data "aws_region" "current" {}

locals {
  tags = merge(var.tags, { Module = "iam" })

  # Zones a workload touches at all need ListBucket / GetBucketLocation.
  bucket_zones = {
    for name, w in var.workloads : name => distinct(concat(w.read_zones, w.write_zones, w.delete_zones))
  }
}

data "aws_iam_policy_document" "assume" {
  for_each = var.workloads

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
      values   = [for sa in each.value.service_accounts : "system:serviceaccount:${each.value.namespace}:${sa}"]
    }

    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "workload" {
  for_each = var.workloads

  name                 = "${var.name_prefix}-${each.key}"
  description          = each.value.description
  assume_role_policy   = data.aws_iam_policy_document.assume[each.key].json
  max_session_duration = 3600
  tags                 = merge(local.tags, { Workload = each.key })
}

data "aws_iam_policy_document" "data_lake" {
  for_each = var.workloads

  dynamic "statement" {
    for_each = length(local.bucket_zones[each.key]) > 0 ? [1] : []
    content {
      sid       = "ListZones"
      effect    = "Allow"
      actions   = ["s3:ListBucket", "s3:GetBucketLocation", "s3:ListBucketMultipartUploads"]
      resources = [for z in local.bucket_zones[each.key] : var.bucket_arns[z]]
    }
  }

  dynamic "statement" {
    for_each = length(each.value.read_zones) > 0 ? [1] : []
    content {
      sid       = "ReadObjects"
      effect    = "Allow"
      actions   = ["s3:GetObject", "s3:GetObjectVersion", "s3:GetObjectTagging"]
      resources = [for z in each.value.read_zones : "${var.bucket_arns[z]}/*"]
    }
  }

  dynamic "statement" {
    for_each = length(each.value.write_zones) > 0 ? [1] : []
    content {
      sid    = "WriteObjects"
      effect = "Allow"
      actions = [
        "s3:PutObject",
        "s3:PutObjectTagging",
        "s3:AbortMultipartUpload",
        "s3:ListMultipartUploadParts",
      ]
      resources = [for z in each.value.write_zones : "${var.bucket_arns[z]}/*"]
    }
  }

  dynamic "statement" {
    for_each = length(each.value.delete_zones) > 0 ? [1] : []
    content {
      sid       = "DeleteObjects"
      effect    = "Allow"
      actions   = ["s3:DeleteObject"]
      resources = [for z in each.value.delete_zones : "${var.bucket_arns[z]}/*"]
    }
  }

  # Multipart uploads to SSE-KMS buckets need Decrypt as well as GenerateDataKey.
  dynamic "statement" {
    for_each = length(local.bucket_zones[each.key]) > 0 ? [1] : []
    content {
      sid    = "UseDataLakeKey"
      effect = "Allow"
      actions = concat(
        ["kms:Decrypt", "kms:DescribeKey"],
        length(each.value.write_zones) > 0 ? ["kms:GenerateDataKey"] : [],
      )
      resources = [var.kms_key_arn]

      condition {
        test     = "StringEquals"
        variable = "kms:ViaService"
        values   = ["s3.${data.aws_region.current.name}.amazonaws.com"]
      }
    }
  }

  # Explicit guard: never allow these roles to change bucket configuration.
  statement {
    sid    = "DenyBucketAdmin"
    effect = "Deny"
    actions = [
      "s3:DeleteBucket*",
      "s3:PutBucket*",
      "s3:PutLifecycleConfiguration",
      "s3:PutEncryptionConfiguration",
      "s3:DeleteObjectVersion",
    ]
    resources = flatten([for arn in values(var.bucket_arns) : [arn, "${arn}/*"]])
  }
}

resource "aws_iam_role_policy" "data_lake" {
  for_each = var.workloads

  name   = "data-lake-access"
  role   = aws_iam_role.workload[each.key].id
  policy = data.aws_iam_policy_document.data_lake[each.key].json
}
