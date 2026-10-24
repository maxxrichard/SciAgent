# ADR-0005: Self-hosted LLM serving with vLLM

- **Status:** Accepted
- **Date:** 2026-02-03

## Context
Prompts include identifiers and summaries of clinical and genomic data that must not leave
our AWS account. We need predictable latency (p95 < 300 ms for planning calls) and cost
control as usage grows.

## Decision
Serve open-weight instruction models with vLLM on the `gpu-inference` node group, exposed
through its OpenAI-compatible API. The agent talks to it through `OpenAICompatibleLLM`, so
the model is a configuration value. A deterministic rule-based planner is the offline
fallback and CI reference.

## Consequences
- Data stays in-account; no third-party processor agreements needed for inference.
- Continuous batching and prefix caching give high throughput per GPU; autoscaling on
  `vllm:num_requests_waiting` matches capacity to demand.
- We own model upgrades; every model change goes through the evaluation gate (ADR-0008).
