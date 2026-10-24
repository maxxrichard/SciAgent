# Environment root module: wires the shared SciAgent modules together.
# The three envs (dev / staging / prod) share this file verbatim; all
# differences live in terraform.tfvars so environments cannot drift
# structurally.

provider "aws" {
  region              = var.region
  allowed_account_ids = var.allowed_account_ids

  default_tags {
    tags = local.tags
  }
}

locals {
  name         = "${var.project}-${var.environment}"
  cluster_name = "${var.project}-${var.environment}"

  tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
    Repository  = "SciAgent/infra/terraform"
  }

  # The api/mcp IRSA roles are bound to service accounts in this namespace;
  # it must match the namespace the Helm release is installed into.
  workloads = {
    api = {
      description      = "SciAgent API / agent orchestrator"
      namespace        = var.app_namespace
      service_accounts = ["sciagent-api"]
      read_zones       = ["curated", "artifacts"]
      write_zones      = ["artifacts"]
    }
    mcp = {
      description      = "SciAgent MCP tool servers (agent tool access)"
      namespace        = var.app_namespace
      service_accounts = ["sciagent-mcp"]
      read_zones       = ["curated"]
    }
    airflow = {
      description      = "Airflow ingestion and harmonisation pipelines"
      namespace        = var.airflow_namespace
      service_accounts = ["airflow-worker", "airflow-scheduler", "airflow-triggerer"]
      read_zones       = ["raw", "curated"]
      write_zones      = ["raw", "curated"]
      delete_zones     = ["curated"]
    }
  }

  node_groups = {
    system = {
      instance_types = ["m6i.large"]
      min_size       = var.system_nodes.min
      max_size       = var.system_nodes.max
      desired_size   = var.system_nodes.desired
      autoscaling    = false
      labels         = { workload = "system" }
    }
    cpu-workers = {
      instance_types = ["m6i.2xlarge"]
      capacity_type  = var.cpu_workers_capacity_type
      min_size       = var.cpu_worker_nodes.min
      max_size       = var.cpu_worker_nodes.max
      desired_size   = var.cpu_worker_nodes.desired
      disk_size_gb   = 100
      labels         = { workload = "cpu-workers" }
    }
    gpu-inference = {
      instance_types = [var.gpu_instance_type]
      ami_type       = "AL2023_x86_64_NVIDIA"
      min_size       = 0
      max_size       = var.gpu_nodes.max
      desired_size   = var.gpu_nodes.desired
      # Room for model weights pulled into the local cache.
      disk_size_gb = 200
      gpu_count    = 1
      labels       = { workload = "gpu-inference" }
      taints = [{
        key    = "nvidia.com/gpu"
        value  = "true"
        effect = "NoSchedule"
      }]
    }
  }
}

module "observability" {
  source = "../../modules/observability"

  name_prefix        = local.name
  environment        = var.environment
  log_retention_days = var.log_retention_days
  oidc_provider_arn  = module.eks.oidc_provider_arn
  oidc_provider_url  = module.eks.oidc_provider_url
  enable_amp         = var.enable_amp
  tags               = local.tags
}

module "network" {
  source = "../../modules/network"

  name                    = local.name
  cluster_name            = local.cluster_name
  vpc_cidr                = var.vpc_cidr
  az_count                = var.az_count
  single_nat_gateway      = var.single_nat_gateway
  interface_endpoints     = var.interface_endpoints
  enable_flow_logs        = true
  flow_logs_log_group_arn = module.observability.vpc_flow_logs_log_group_arn
  tags                    = local.tags
}

module "eks" {
  source = "../../modules/eks"

  cluster_name                 = local.cluster_name
  kubernetes_version           = var.kubernetes_version
  private_subnet_ids           = module.network.private_subnet_ids
  endpoint_public_access       = var.eks_endpoint_public_access
  endpoint_public_access_cidrs = var.eks_endpoint_public_access_cidrs
  admin_role_arns              = var.eks_admin_role_arns
  node_groups                  = local.node_groups
  log_retention_days           = var.log_retention_days
  logs_kms_key_arn             = module.observability.logs_kms_key_arn
  tags                         = local.tags
}

module "data_lake" {
  source = "../../modules/data_lake"

  name_prefix   = local.name
  force_destroy = var.data_lake_force_destroy
  tags          = local.tags
}

module "database" {
  source = "../../modules/database"

  identifier                          = local.name
  vpc_id                              = module.network.vpc_id
  subnet_ids                          = module.network.private_subnet_ids
  allowed_security_groups             = { eks-nodes = module.eks.cluster_security_group_id }
  instance_class                      = var.db_instance_class
  allocated_storage_gb                = var.db_allocated_storage_gb
  max_allocated_storage_gb            = var.db_max_allocated_storage_gb
  multi_az                            = var.db_multi_az
  backup_retention_days               = var.db_backup_retention_days
  deletion_protection                 = var.db_deletion_protection
  performance_insights_retention_days = var.db_performance_insights_retention_days
  tags                                = local.tags
}

module "iam" {
  source = "../../modules/iam"

  name_prefix       = local.name
  oidc_provider_arn = module.eks.oidc_provider_arn
  oidc_provider_url = module.eks.oidc_provider_url
  bucket_arns       = module.data_lake.bucket_arns
  kms_key_arn       = module.data_lake.kms_key_arn
  workloads         = local.workloads
  tags              = local.tags
}
