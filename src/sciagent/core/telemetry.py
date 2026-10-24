"""Prometheus metrics shared by every service.

Metric names are part of the operational contract: SLO recording rules and
Grafana dashboards in ``deploy/monitoring`` depend on them.
"""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Histogram

REGISTRY = CollectorRegistry(auto_describe=True)

HTTP_REQUESTS = Counter(
    "sciagent_http_requests_total",
    "HTTP requests handled.",
    ["service", "method", "route", "status"],
    registry=REGISTRY,
)
HTTP_LATENCY = Histogram(
    "sciagent_http_request_duration_seconds",
    "HTTP request latency.",
    ["service", "method", "route"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.2, 0.3, 0.5, 1, 2.5, 5, 10),
    registry=REGISTRY,
)
TOOL_CALLS = Counter(
    "sciagent_tool_calls_total",
    "Agent tool invocations.",
    ["tool", "outcome"],
    registry=REGISTRY,
)
TOOL_LATENCY = Histogram(
    "sciagent_tool_call_duration_seconds",
    "Tool invocation latency.",
    ["tool"],
    registry=REGISTRY,
)
AGENT_RUN_DURATION = Histogram(
    "sciagent_agent_run_duration_seconds",
    "End-to-end agent run duration.",
    ["status"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60, 120),
    registry=REGISTRY,
)
LLM_TOKENS = Counter(
    "sciagent_llm_tokens_total",
    "LLM tokens consumed.",
    ["kind"],
    registry=REGISTRY,
)
GUARDRAIL_BLOCKS = Counter(
    "sciagent_guardrail_blocks_total",
    "Requests or outputs blocked by guardrails.",
    ["rule", "stage"],
    registry=REGISTRY,
)
PIPELINE_FAILURES = Counter(
    "sciagent_pipeline_failures_total",
    "Data pipeline task failures.",
    ["pipeline"],
    registry=REGISTRY,
)
