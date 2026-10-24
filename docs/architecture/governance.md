# Governance

## Tool policy

`sciagent/governance/policies.yaml` is the single source of truth for which principals may
call which tools. Unknown tools are denied by default.

| Attribute | Effect |
|---|---|
| `group` | Caller must belong to the data group (`imaging`, `genomics`, `clinical`) |
| `roles` | Allowed roles (`researcher`, `analyst`, `admin`) |
| `classification` | `restricted` tools require an admin |
| `max_calls_per_run` | Per-run budget to bound cost and runaway loops |
| `max_rows` | Upper bound on `limit` arguments |

## Audit log

Every authorisation decision, direct tool call, dataset registration and guardrail event is
appended to `audit_events`. Each row stores `prev_hash` and
`hash = sha256(prev_hash || canonical_json(event))`; `GET /v1/audit/verify` and
`sciagent audit-verify` replay the chain and return the first tampered sequence number.

## Guardrails

| Stage | Check | Action |
|---|---|---|
| Input | prompt injection patterns | block |
| Input | PII (email, phone, IBAN, DOB) | block |
| Input | > 4 000 characters | block |
| Output | PII | redact |
| Output | numbers not traceable to tool outputs or the question | flag in answer |

All guardrail events increment `sciagent_guardrail_blocks_total{rule,stage}`.
