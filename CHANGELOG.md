# Changelog

All notable changes are documented here; the format follows Keep a Changelog.

## [0.9.0] - 2026-10-24

### Added
- LangGraph agent with input/output guardrails, policy-checked tool calls and audit trail.
- Eight scientific tools served by imaging, genomics and clinical MCP servers.
- FastAPI service: agent runs, dataset catalog, direct tool calls, semantic search, audit.
- 40 declarative data pipelines with quality gates, versioned Parquet/Delta publishing and
  generated Airflow DAGs.
- Evaluation harness with curated tasks, LLM-as-judge, human review queue and release gate.
- Terraform for AWS (VPC, EKS with GPU node group, S3, RDS, IRSA), Helm chart, Prometheus
  SLO rules and Grafana dashboard.
