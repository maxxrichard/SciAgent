# Security policy

Please report vulnerabilities privately via GitHub Security Advisories on this repository
rather than opening a public issue. Include steps to reproduce and the affected version.

Security-relevant design:

- Authentication by API key (SHA-256 digests in memory, constant-time comparison).
- Default-deny tool policy and a hash-chained audit log (`docs/architecture/governance.md`).
- Containers run as non-root with read-only root filesystems; NetworkPolicies restrict
  MCP servers and vLLM to traffic from the API.
- Least-privilege IRSA roles per workload; S3 and RDS encrypted with KMS.
