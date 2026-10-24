# SciAgent

SciAgent is a platform where scientists query, harmonise and analyse multimodal
biological data — microscopy imaging, genomics and clinical time series — through
agentic workflows. Tools are governed, every decision is audited, and every release
is gated by an evaluation suite.

!!! tip "Five-minute tour"
    `make install && make test && make eval`, then
    `.venv/bin/sciagent query "How many nuclei are in IMG-0007?"`.
    See [Getting started](guides/getting-started.md).

## Principles

1. **Reliable utility, not a demo.** SLOs, runbooks and on-call ownership from day one.
2. **Governed by construction.** The planner proposes; the policy engine disposes. No tool
   runs without an allow decision in the audit log.
3. **Reproducible.** Datasets are versioned and content-hashed; tools are deterministic
   functions of their inputs; agent runs persist every step.
4. **Measured.** Behaviour changes ship only when the evaluation gate passes.

## Where to go next

- [Architecture overview](architecture/overview.md)
- [Architecture decisions](adr/README.md)
- [Runbooks](runbooks/README.md) and the [risk register](risk-register.md)
