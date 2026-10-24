# ADR-0002: Run the platform on Kubernetes (EKS)

- **Status:** Accepted
- **Date:** 2026-01-14

## Context
We need to run stateless services (API, MCP servers), GPU inference, and batch pipelines
with independent scaling, isolation between research groups' workloads, and reproducible
environments for dev, staging and prod.

## Decision
Use Amazon EKS with three managed node groups — `system`, `cpu-workers` and a tainted
`gpu-inference` group — provisioned by Terraform. Workloads are packaged as one Helm chart.
IAM access to S3 and Secrets Manager uses IRSA with one role per workload.

## Consequences
- GPU capacity can scale to zero in dev and scale on queue depth in prod.
- One deployment model for services, inference and Airflow workers.
- We take on Kubernetes operational complexity; mitigated with managed node groups,
  managed add-ons and a single chart.

## Alternatives considered
- **ECS/Fargate:** simpler, but weaker GPU scheduling and no first-class operator ecosystem.
- **SageMaker endpoints for inference:** easy to start, but higher per-hour GPU cost and a
  second deployment model.
