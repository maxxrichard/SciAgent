/**
 * data_lake: medallion-style S3 zones for multimodal biological data.
 *
 *   raw        - immutable landing zone (instrument output, VCF/FASTQ, DICOM, EHR extracts)
 *   curated    - harmonised, validated datasets (Parquet / Zarr / OME-Zarr)
 *   artifacts  - analysis outputs, agent run artefacts, model files
 *
 * All buckets: versioning, SSE-KMS with a customer-managed key, public access
 * blocked, TLS >= 1.2 enforced by bucket policy, lifecycle tiering.
 */

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  tags = merge(var.tags, { Module = "data_lake" })

  # Account ID suffix keeps bucket names globally unique without random strings.
  bucket_names = {
    for zone in keys(var.zones) :
    zone => "${var.name_prefix}-${zone}-${data.aws_caller_identity.current.account_id}"
  }
}

# --- Encryption --------------------------------------------------------------

data "aws_iam_policy_document" "kms" {
  # Account root retains full control so IAM policies can delegate key use.
  statement {
    sid       = "EnableRootAccount"
    effect    = "Allow"
    actions   = ["kms:*"]
    resources = ["*"]

    principals {
      type        = "AWS"
      identifiers = ["arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
  }
  # Workload access is granted in IAM (see the iam module), scoped by
  # kms:ViaService so the key is only usable through S3.
}

resource "aws_kms_key" "data_lake" {
  description             = "${var.name_prefix} data lake SSE-KMS key"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  policy                  = data.aws_iam_policy_document.kms.json
  tags                    = local.tags
}

resource "aws_kms_alias" "data_lake" {
  name          = "alias/${var.name_prefix}-data-lake"
  target_key_id = aws_kms_key.data_lake.key_id
}

# --- Access-log bucket (S3 server access logs only support SSE-S3) ----------

resource "aws_s3_bucket" "logs" {
  bucket        = "${var.name_prefix}-s3-access-logs-${data.aws_caller_identity.current.account_id}"
  force_destroy = var.force_destroy
  tags          = merge(local.tags, { Zone = "logs" })
}

resource "aws_s3_bucket_public_access_block" "logs" {
  bucket                  = aws_s3_bucket.logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "logs" {
  bucket = aws_s3_bucket.logs.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "logs" {
  bucket = aws_s3_bucket.logs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "logs" {
  bucket = aws_s3_bucket.logs.id

  rule {
    id     = "expire-access-logs"
    status = "Enabled"
    filter {}

    expiration {
      days = var.access_log_retention_days
    }
  }
}

data "aws_iam_policy_document" "logs" {
  statement {
    sid       = "S3ServerAccessLogsPolicy"
    effect    = "Allow"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.logs.arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["logging.s3.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }

  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.logs.arn, "${aws_s3_bucket.logs.arn}/*"]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "logs" {
  bucket = aws_s3_bucket.logs.id
  policy = data.aws_iam_policy_document.logs.json

  depends_on = [aws_s3_bucket_public_access_block.logs]
}

# --- Data-lake zone buckets --------------------------------------------------

resource "aws_s3_bucket" "zone" {
  for_each = var.zones

  bucket        = local.bucket_names[each.key]
  force_destroy = var.force_destroy
  tags          = merge(local.tags, { Zone = each.key })
}

resource "aws_s3_bucket_public_access_block" "zone" {
  for_each = var.zones

  bucket                  = aws_s3_bucket.zone[each.key].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "zone" {
  for_each = var.zones

  bucket = aws_s3_bucket.zone[each.key].id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_versioning" "zone" {
  for_each = var.zones

  bucket = aws_s3_bucket.zone[each.key].id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "zone" {
  for_each = var.zones

  bucket = aws_s3_bucket.zone[each.key].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.data_lake.arn
    }
    # S3 Bucket Keys cut KMS request costs by ~99% for high-object-count zones.
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_logging" "zone" {
  for_each = var.zones

  bucket        = aws_s3_bucket.zone[each.key].id
  target_bucket = aws_s3_bucket.logs.id
  target_prefix = "${each.key}/"
}

resource "aws_s3_bucket_lifecycle_configuration" "zone" {
  for_each = var.zones

  bucket = aws_s3_bucket.zone[each.key].id

  rule {
    id     = "tiering"
    status = "Enabled"
    filter {}

    transition {
      days          = each.value.transition_ia_days
      storage_class = "STANDARD_IA"
    }

    dynamic "transition" {
      for_each = each.value.transition_glacier_days != null ? [each.value.transition_glacier_days] : []
      content {
        days          = transition.value
        storage_class = "GLACIER_IR"
      }
    }

    dynamic "transition" {
      for_each = each.value.transition_deep_archive_days != null ? [each.value.transition_deep_archive_days] : []
      content {
        days          = transition.value
        storage_class = "DEEP_ARCHIVE"
      }
    }

    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "STANDARD_IA"
    }

    noncurrent_version_expiration {
      noncurrent_days = each.value.noncurrent_expiration_days
    }
  }

  rule {
    id     = "abort-incomplete-multipart"
    status = "Enabled"
    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  depends_on = [aws_s3_bucket_versioning.zone]
}

data "aws_iam_policy_document" "zone" {
  for_each = var.zones

  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.zone[each.key].arn, "${aws_s3_bucket.zone[each.key].arn}/*"]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  statement {
    sid       = "DenyOutdatedTLS"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.zone[each.key].arn, "${aws_s3_bucket.zone[each.key].arn}/*"]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "NumericLessThan"
      variable = "s3:TlsVersion"
      values   = ["1.2"]
    }
  }

  # Reject uploads that explicitly request a different encryption mode / key.
  statement {
    sid       = "DenyWrongKmsKey"
    effect    = "Deny"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.zone[each.key].arn}/*"]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Null"
      variable = "s3:x-amz-server-side-encryption-aws-kms-key-id"
      values   = ["false"]
    }

    condition {
      test     = "StringNotEquals"
      variable = "s3:x-amz-server-side-encryption-aws-kms-key-id"
      values   = [aws_kms_key.data_lake.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "zone" {
  for_each = var.zones

  bucket = aws_s3_bucket.zone[each.key].id
  policy = data.aws_iam_policy_document.zone[each.key].json

  depends_on = [aws_s3_bucket_public_access_block.zone]
}
