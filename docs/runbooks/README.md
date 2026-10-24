# Runbooks

Each alert in `deploy/monitoring/prometheus/rules` links here. Every runbook follows the
same shape: **Impact → Diagnose → Mitigate → Follow up**.

- [API availability burn rate](#api-availability-burn-rate)
- [API latency](#api-latency)
- [LLM serving latency / queue](#llm-serving-latency-queue)
- [Tool error ratio](#tool-error-ratio)
- [Guardrail block spike](#guardrail-block-spike)
- [Pipeline failures](#pipeline-failures)
- [GPU under-utilised](#gpu-under-utilised)
- [Audit chain broken](#audit-chain-broken)

## API availability burn rate

**Impact:** researchers receive 5xx responses; the 99.9% error budget is being consumed.

**Diagnose**
1. Grafana → *SciAgent overview* → error ratio by route. Is it one route or all?
2. `kubectl -n sciagent get pods -l app.kubernetes.io/component=api` — restarts, OOMKills?
3. `/readyz` reports the failing dependency (`database`, `tools`).
4. 502s on `/v1/query` usually mean a tool server or vLLM is failing — check those panels.

**Mitigate:** roll back with `helm rollback sciagent -n sciagent`; scale the API; fail over
RDS if the database check is red.

**Follow up:** postmortem if more than 25% of the monthly budget was burned.

## API latency

**Diagnose:** split p95 by route. `/v1/query` latency is dominated by LLM and tool calls —
compare `sciagent_tool_call_duration_seconds` and vLLM latency. Other routes point at the
database (check RDS Performance Insights).

**Mitigate:** scale API/MCP replicas; reduce `SCIAGENT_AGENT_MAX_STEPS` temporarily.

## LLM serving latency / queue

**Diagnose:** `vllm:num_requests_waiting` rising with flat replica count means the HPA is
capped or GPU nodes cannot be scheduled (`kubectl get nodes -l workload=gpu-inference`,
cluster-autoscaler logs, EC2 capacity for `g5`).

**Mitigate:** raise `vllm.autoscaling.maxReplicas`; as a last resort set
`SCIAGENT_LLM_BACKEND=rule` on the API to fall back to the deterministic planner.

## Tool error ratio

**Diagnose:** `sciagent_tool_calls_total{outcome="error"}` by `tool`. `invalid` outcomes
mean the planner is producing bad arguments (check recent model/prompt changes and the
latest evaluation report); `error` outcomes mean the tool itself failed (MCP server logs).

**Mitigate:** roll back the offending MCP server or model; remove the tool from
`policies.yaml` to disable it platform-wide.

## Guardrail block spike

**Diagnose:** `sciagent_guardrail_blocks_total` by `rule`. Query recent
`guardrail.input` audit events (`GET /v1/audit/events`) to see whether this is abuse,
a client bug, or a false positive (e.g. a new identifier format matching a PII pattern).

**Mitigate:** for false positives, add a guardrail unit test reproducing it, fix the
pattern, and ship through the eval gate.

## Pipeline failures

**Diagnose:** Airflow UI → failing DAG `sciagent__<pipeline>`. `quality_gate` failures
list the violated checks; `publish` failures are usually S3/IRSA permissions or schema
changes.

**Mitigate:** the previous dataset version remains current in the catalog, so consumers
are unaffected. Fix the source or the check, then clear the task.

## GPU under-utilised

**Impact:** cost, not availability.

**Diagnose:** `DCGM_FI_DEV_GPU_UTIL` per node vs. request rate. Common causes: HPA
`minReplicas` too high after a load test; a stuck pod holding a GPU.

**Mitigate:** lower `minReplicas` (dev: 0); delete stuck pods.

## Audit chain broken

**Impact:** possible tampering with the audit trail — treat as a security incident.

1. Run `sciagent audit-verify` to get the first bad sequence number.
2. Restrict write access to the database; snapshot RDS immediately.
3. Compare the affected rows against the latest RDS snapshot and CloudTrail/RDS logs.
4. Notify the security officer; do **not** "repair" the chain in place.
