# prod: NAT per AZ, multi-AZ RDS on memory-optimised instances, private
# endpoints for ECR/STS/logs, long retention, managed Prometheus.
environment = "prod"
region      = "eu-central-1"

# Replace with the prod AWS account ID before the first plan.
allowed_account_ids = ["333333333333"]

vpc_cidr            = "10.30.0.0/16"
az_count            = 3
single_nat_gateway  = false
interface_endpoints = ["ecr.api", "ecr.dkr", "sts", "logs", "secretsmanager"]

kubernetes_version         = "1.33"
eks_endpoint_public_access = true
# Restrict to the corporate VPN / CI egress ranges.
eks_endpoint_public_access_cidrs = ["0.0.0.0/0"]
eks_admin_role_arns              = []

system_nodes              = { min = 3, max = 6, desired = 3 }
cpu_worker_nodes          = { min = 3, max = 20, desired = 3 }
cpu_workers_capacity_type = "ON_DEMAND"
gpu_instance_type         = "g5.2xlarge"
gpu_nodes                 = { max = 6, desired = 1 }

data_lake_force_destroy = false

db_instance_class                      = "db.r6g.xlarge"
db_allocated_storage_gb                = 200
db_max_allocated_storage_gb            = 2000
db_multi_az                            = true
db_backup_retention_days               = 30
db_deletion_protection                 = true
db_performance_insights_retention_days = 31

log_retention_days = 365
enable_amp         = true
