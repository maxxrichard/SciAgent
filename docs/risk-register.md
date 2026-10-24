# Risk register

Reviewed at every release planning meeting. Likelihood (L) and impact (I) are 1–5;
score = L × I. Owner is the accountable role.

| ID | Risk | L | I | Score | Mitigation | Owner | Status |
|---|---|---|---|---|---|---|---|
| R1 | Agent states figures not supported by any analysis (hallucination) | 3 | 5 | 15 | Numeric-grounding output guardrail; `numeric_grounding` gate ≥ 95%; answers show tool steps | Lead engineer | Mitigated |
| R2 | Researcher accesses data outside their group via the agent | 2 | 5 | 10 | Policy engine on every call, default deny, governance eval tasks at 100%, audit log | Lead engineer | Mitigated |
| R3 | Prompt injection via questions or retrieved documents | 3 | 4 | 12 | Input guardrails; authorisation is structural (graph edge), not prompt-based; tools are read-only | Lead engineer | Mitigated |
| R4 | GPU scheduling contention delays inference | 3 | 3 | 9 | Dedicated tainted GPU node group; queue-depth autoscaling; rule-based fallback | Platform | Mitigated |
| R5 | GPU cost overrun | 3 | 3 | 9 | Scale-to-zero in dev; under-utilisation alert; cost-per-query dashboard | Platform | Monitoring |
| R6 | Data-access bottleneck from small files / cross-AZ reads on S3 | 3 | 3 | 9 | Columnar Parquet with zstd; scheduled compaction; VPC gateway endpoint for S3 | Data | Mitigated |
| R7 | Model upgrade silently degrades answer quality | 3 | 4 | 12 | Eval-gated releases (ADR-0008); LLM-judge run against staging before prod | Lead engineer | Mitigated |
| R8 | PII leaks into logs or answers | 2 | 5 | 10 | Input PII blocking, output redaction, pseudonymised identifiers in all datasets | Security | Mitigated |
| R9 | Audit trail tampering | 1 | 5 | 5 | Hash chain with verification endpoint; RDS snapshots; least-privilege DB roles | Security | Mitigated |
| R10 | Single-person knowledge concentration | 3 | 3 | 9 | ADRs, runbooks, MkDocs, pairing on on-call | Lead engineer | Open |
| R11 | Upstream dependency breaking change (LangGraph, MCP SDK) | 3 | 2 | 6 | Pinned lower bounds, Dependabot, integration tests over in-process MCP | Lead engineer | Monitoring |
