# dev: cost-optimised. Single NAT, small nodes, single-AZ RDS, short retention.
environment = "dev"
region      = "eu-central-1"

# Replace with the dev AWS account ID before the first plan.
allowed_account_ids = ["111111111111"]

vpc_cidr            = "10.10.0.0/16"
az_count            = 3
single_nat_gateway  = true
interface_endpoints = []

kubernetes_version               = "1.33"
eks_endpoint_public_access       = true
eks_endpoint_public_access_cidrs = ["0.0.0.0/0"]
eks_admin_role_arns              = []

system_nodes              = { min = 2, max = 3, desired = 2 }
cpu_worker_nodes          = { min = 0, max = 4, desired = 1 }
cpu_workers_capacity_type = "SPOT"
gpu_instance_type         = "g5.2xlarge"
gpu_nodes                 = { max = 1, desired = 0 }

data_lake_force_destroy = true

db_instance_class                      = "db.t4g.medium"
db_allocated_storage_gb                = 20
db_max_allocated_storage_gb            = 100
db_multi_az                            = false
db_backup_retention_days               = 3
db_deletion_protection                 = false
db_performance_insights_retention_days = 7

log_retention_days = 14
enable_amp         = false
