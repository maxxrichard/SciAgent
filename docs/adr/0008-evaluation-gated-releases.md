# ADR-0008: Evaluation-gated releases

- **Status:** Accepted
- **Date:** 2026-02-24

## Context
Prompt, model and tool changes can silently degrade answers. Unit tests do not catch
"the agent picked the wrong analysis" or "the agent stated a number it did not compute".

## Decision
Maintain a curated task suite (categories: imaging, genomics, clinical, harmonisation,
governance, safety). Each task is checked automatically (status, tool selection, policy
enforcement, numeric grounding against reference tool calls) and graded by an LLM judge
against a rubric. Low-confidence results go to a human review queue. Releases are blocked
unless thresholds in `evals/gate.yaml` are met; safety and governance require 100%.

## Consequences
- Regressions are caught before deploy, and every release has an evaluation report.
- Curating tasks is ongoing work, owned by the groups who use the platform.
- The judge itself can drift; its agreement with human reviewers is tracked per release.
