# ADR-0001: Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-01-12

## Context
The platform is built by a small team for several research groups over multiple years.
Decisions made early (cluster, serving stack, data formats) constrain everything after,
and the reasoning is easily lost.

## Decision
We keep lightweight ADRs in `docs/adr/`, one file per decision, with Context, Decision,
Consequences and Alternatives. Any change touching more than one component, adding an
external dependency, or changing a security boundary requires an ADR in the same PR.

## Consequences
Design reviews have a written artefact to review. New contributors can read why things are
the way they are. The cost is a short document per significant change.
