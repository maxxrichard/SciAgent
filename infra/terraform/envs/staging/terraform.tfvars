# staging: production topology (multi-AZ NAT + RDS) at reduced capacity.
environment = "staging"
region      = "eu-central-1"

# Replace with the staging AWS account ID before the first plan.
allowed_account_ids = ["222222222222"]

vpc_cidr            = "10.20.0.0/16"
az_count            = 3
single_nat_gateway  = false
interface_endpoints = ["ecr.api", "ecr.dkr", "sts"]

kubernetes_version               = "1.33"
eks_endpoint_public_access       = true
eks_endpoint_public_access_cidrs = ["0.0.0.0/0"]
eks_admin_role_arns              = []

system_nodes              = { min = 2, max = 4, desired = 2 }
cpu_worker_nodes          = { min = 1, max = 6, desired = 2 }
cpu_workers_capacity_type = "ON_DEMAND"
gpu_instance_type         = "g5.2xlarge"
gpu_nodes                 = { max = 2, desired = 0 }

data_lake_force_destroy = false

db_instance_class                      = "db.r6g.large"
db_allocated_storage_gb                = 50
db_max_allocated_storage_gb            = 250
db_multi_az                            = true
db_backup_retention_days               = 7
db_deletion_protection                 = true
db_performance_insights_retention_days = 7

log_retention_days = 30
enable_amp         = false
