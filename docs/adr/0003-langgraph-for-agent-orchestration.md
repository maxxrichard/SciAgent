# ADR-0003: LangGraph for agent orchestration

- **Status:** Accepted
- **Date:** 2026-01-20

## Context
Agent behaviour must be inspectable and governable: every tool call has to pass an
authorisation step that the model cannot skip, runs need step limits, and we need to test
individual transitions.

## Decision
Model the agent as an explicit LangGraph `StateGraph` with nodes for input guardrails,
retrieval, planning, authorisation, execution and output guardrails. Authorisation is a
graph edge, not a prompt instruction.

## Consequences
- Governance is structural: there is no path from `plan` to `act` that bypasses `authorize`.
- Each node is a plain method, unit-testable with scripted LLM responses.
- We depend on LangGraph's state/reducer semantics; the graph is small enough to port.

## Alternatives considered
- **Free-form ReAct loop:** less code, but governance would rely on prompt compliance.
- **Hand-written state machine:** viable; LangGraph gives us checkpointing and streaming
  without maintaining them ourselves.
