/**
 * database: RDS for PostgreSQL 16 (metadata catalogue, agent run state,
 * pgvector embeddings) in private subnets.
 *
 * pgvector ships with RDS PostgreSQL 16 and needs no shared_preload_libraries
 * entry; enable it once per database with `CREATE EXTENSION IF NOT EXISTS vector;`.
 *
 * The master password is generated and rotated by RDS and stored in Secrets
 * Manager (manage_master_user_password), encrypted with a dedicated KMS key.
 */

data "aws_partition" "current" {}

locals {
  tags = merge(var.tags, { Module = "database" })
}

resource "aws_kms_key" "db" {
  description             = "${var.identifier} RDS storage, Performance Insights and secret encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  tags                    = local.tags
}

resource "aws_kms_alias" "db" {
  name          = "alias/${var.identifier}-rds"
  target_key_id = aws_kms_key.db.key_id
}

resource "aws_db_subnet_group" "this" {
  name        = var.identifier
  description = "Private subnets for ${var.identifier}"
  subnet_ids  = var.subnet_ids
  tags        = local.tags
}

resource "aws_security_group" "db" {
  name        = "${var.identifier}-rds"
  description = "PostgreSQL access from EKS workloads"
  vpc_id      = var.vpc_id
  tags        = merge(local.tags, { Name = "${var.identifier}-rds" })
}

resource "aws_vpc_security_group_ingress_rule" "from_sg" {
  # Static keys so for_each works even when SG IDs are unknown until apply.
  for_each = var.allowed_security_groups

  security_group_id            = aws_security_group.db.id
  description                  = "PostgreSQL from ${each.key}"
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  referenced_security_group_id = each.value
}

resource "aws_db_parameter_group" "this" {
  name_prefix = "${var.identifier}-pg16-"
  family      = "postgres16"
  description = "SciAgent PostgreSQL 16 parameters"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = tostring(var.log_min_duration_statement_ms)
  }

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }

  # pg_stat_statements is preloaded by default on RDS; keep it tracking
  # nested statements so agent-generated SQL is attributable.
  parameter {
    name  = "pg_stat_statements.track"
    value = "all"
  }

  # Larger maintenance memory speeds up HNSW / IVFFlat index builds for pgvector.
  parameter {
    name         = "maintenance_work_mem"
    value        = tostring(var.maintenance_work_mem_kb)
    apply_method = "pending-reboot"
  }

  tags = local.tags

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_iam_role" "monitoring" {
  name = "${var.identifier}-rds-monitoring"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "monitoring.rds.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "monitoring" {
  role       = aws_iam_role.monitoring.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

resource "aws_db_instance" "this" {
  identifier     = var.identifier
  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  db_name  = var.database_name
  username = var.master_username

  manage_master_user_password   = true
  master_user_secret_kms_key_id = aws_kms_key.db.arn

  allocated_storage     = var.allocated_storage_gb
  max_allocated_storage = var.max_allocated_storage_gb
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = aws_kms_key.db.arn

  multi_az               = var.multi_az
  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.db.id]
  publicly_accessible    = false
  port                   = 5432

  parameter_group_name                = aws_db_parameter_group.this.name
  iam_database_authentication_enabled = true

  backup_retention_period  = var.backup_retention_days
  backup_window            = "02:00-03:00"
  maintenance_window       = "sun:03:30-sun:04:30"
  copy_tags_to_snapshot    = true
  delete_automated_backups = false

  auto_minor_version_upgrade  = true
  allow_major_version_upgrade = false
  apply_immediately           = var.apply_immediately

  performance_insights_enabled          = true
  performance_insights_kms_key_id       = aws_kms_key.db.arn
  performance_insights_retention_period = var.performance_insights_retention_days

  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.monitoring.arn

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = !var.deletion_protection
  final_snapshot_identifier = var.deletion_protection ? "${var.identifier}-final" : null

  tags = local.tags

  depends_on = [aws_iam_role_policy_attachment.monitoring]
}
