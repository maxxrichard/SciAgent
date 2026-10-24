# SciAgent infrastructure (Terraform)

AWS infrastructure for the SciAgent platform: an EKS cluster with CPU and GPU
node pools, an S3 data lake for multimodal biological data, RDS PostgreSQL 16
(with pgvector) and least-privilege IRSA roles for the workloads deployed by
`deploy/helm/sciagent`.

## Layout

```
infra/terraform/
├── bootstrap/            # one-time per account: state bucket, lock table, GitHub OIDC roles
├── modules/
│   ├── network/          # VPC, 3-AZ public/private subnets, NAT, S3 gateway + interface endpoints, flow logs
│   ├── eks/              # EKS control plane, node groups, OIDC provider (IRSA), add-ons
│   ├── data_lake/        # raw / curated / artifacts buckets, SSE-KMS, lifecycle, TLS-only policies
│   ├── database/         # RDS PostgreSQL 16, Secrets Manager credentials, KMS
│   ├── iam/              # IRSA roles: api, mcp, airflow
│   └── observability/    # KMS-encrypted CloudWatch log groups, Fluent Bit IRSA, optional AMP
└── envs/
    ├── dev/              # single NAT, spot cpu-workers, single-AZ RDS
    ├── staging/          # prod topology, reduced capacity
    └── prod/             # NAT per AZ, multi-AZ r6g RDS, interface endpoints, AMP
```

Every env has the same `main.tf`, `variables.tf`, `outputs.tf` and
`versions.tf`; only `terraform.tfvars` and `backend.tf` differ. Keep the shared
files identical (CI diffs them implicitly by validating all three) and express
environment differences as variables.

### What gets created

| Module | Key resources |
| --- | --- |
| network | `/16` VPC, `/20` private + `/24` public subnets in 3 AZs, NAT gateway(s), S3 gateway endpoint, optional ECR/STS/logs/Secrets Manager interface endpoints, REJECT flow logs |
| eks | EKS (`API` auth mode, secrets envelope-encrypted with KMS, all control-plane logs), managed node groups, IAM OIDC provider, add-ons `vpc-cni`, `kube-proxy`, `coredns`, `eks-pod-identity-agent`, `aws-ebs-csi-driver` |
| data_lake | `sciagent-<env>-{raw,curated,artifacts}-<account>` buckets: versioning, SSE-KMS with bucket keys, BucketOwnerEnforced, public access blocked, TLS >= 1.2 enforced, lifecycle to STANDARD_IA / GLACIER_IR / DEEP_ARCHIVE, access logging |
| database | RDS PostgreSQL 16, `rds.force_ssl=1`, gp3 with storage autoscaling, Performance Insights, enhanced monitoring, RDS-managed master secret in Secrets Manager |
| iam | IRSA roles bound to specific service accounts (see below) |
| observability | `/sciagent/<env>/<component>` log groups, logs KMS key, Fluent Bit IRSA role, optional Amazon Managed Prometheus workspace + remote-write role |

### Node groups

| Name | Instance | Scaling | Scheduling |
| --- | --- | --- | --- |
| `system` | m6i.large | fixed | label `workload=system` |
| `cpu-workers` | m6i.2xlarge | cluster-autoscaler | label `workload=cpu-workers` |
| `gpu-inference` | g5.2xlarge (AL2023 NVIDIA AMI) | cluster-autoscaler, **min 0** | label `workload=gpu-inference`, taint `nvidia.com/gpu=true:NoSchedule` |

The ASGs carry `k8s.io/cluster-autoscaler/node-template/*` tags for labels,
taints and `nvidia.com/gpu`, so cluster-autoscaler can scale the GPU pool up
from zero when a vLLM pod is pending. Nodes enforce IMDSv2 with hop limit 1,
so pods cannot use the node role and must use IRSA.

### IRSA roles

| Role | Service accounts | Data lake access |
| --- | --- | --- |
| `sciagent-<env>-api` | `sciagent/sciagent-api` | read `curated`, read/write `artifacts` |
| `sciagent-<env>-mcp` | `sciagent/sciagent-mcp` | read `curated` |
| `sciagent-<env>-airflow` | `airflow/airflow-{worker,scheduler,triggerer}` | read/write `raw` and `curated`, delete on `curated` only |

KMS permissions are scoped with `kms:ViaService = s3.<region>.amazonaws.com`,
and every role carries an explicit deny on bucket-configuration changes and
`s3:DeleteObjectVersion`. Service account names must match
`deploy/helm/sciagent/values.yaml` (`api.serviceAccount.name`,
`mcp.serviceAccount.name`).

## Bootstrap (once per account / environment)

```bash
cd infra/terraform/bootstrap
terraform init
terraform apply -var environment=dev -var github_repository=<owner>/SciAgent
# For a second env in the same account: -var create_github_oidc_provider=false
```

This creates `sciagent-tfstate-<env>` (S3), `sciagent-tfstate-<env>-lock`
(DynamoDB) and two GitHub OIDC roles. Store the outputs as GitHub secrets:

| Secret | Scope | Value |
| --- | --- | --- |
| `AWS_PLAN_ROLE_ARN_DEV` / `_STAGING` / `_PROD` | repository | `github_plan_role_arn` |
| `AWS_APPLY_ROLE_ARN` | GitHub environment `dev` / `staging` / `prod` | `github_apply_role_arn` |

Configure required reviewers on the `prod` GitHub environment; the apply role
for prod can only be assumed by jobs bound to that environment.

Then set `allowed_account_ids` (and ideally `eks_endpoint_public_access_cidrs`
and `eks_admin_role_arns`) in `envs/<env>/terraform.tfvars`.

## Plan / apply

```bash
cd infra/terraform/envs/dev
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

CI (`.github/workflows/terraform.yml`):

1. **PRs touching `infra/**`**: `terraform fmt -check`, `init -backend=false`
   + `validate` for dev/staging/prod, and `tflint`.
2. **Push to `main`**: `terraform plan` per environment using the read-only
   OIDC plan role; the plan is uploaded as an artifact.
3. **Apply**: runs after the plan, bound to the GitHub environment of the same
   name. `prod` requires manual approval through the environment protection
   rule.

## After the first apply

```bash
# kubeconfig
$(terraform output -raw kubeconfig_command)

# pgvector (no shared_preload_libraries change needed on RDS PostgreSQL 16)
psql "host=$(terraform output -raw database_endpoint | cut -d: -f1) dbname=sciagent sslmode=require user=sciagent_admin" \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"

# values for the Helm chart
terraform output helm_values
```

The master credentials live in Secrets Manager
(`terraform output database_master_secret_arn`). Create a least-privilege
application role in PostgreSQL and expose `SCIAGENT_DATABASE_URL` and
`SCIAGENT_API_KEYS` through a Kubernetes Secret (for example via External
Secrets Operator); the chart only references that Secret by name
(`secrets.existingSecret`).

Cluster add-ons that are not EKS-managed (cluster-autoscaler, AWS Load
Balancer Controller, NVIDIA device plugin / GPU operator with DCGM exporter,
kube-prometheus-stack, Fluent Bit) are installed with Helm after the cluster
exists and are not part of this Terraform.

## Conventions

- Terraform `>= 1.6`, AWS provider `~> 5.0`.
- Resource names: `sciagent-<env>-<thing>`.
- All data at rest is encrypted with customer-managed KMS keys with rotation.
- `default_tags` set `Project`, `Environment`, `ManagedBy` on everything.
- Run `terraform fmt -recursive infra/terraform` before committing.
