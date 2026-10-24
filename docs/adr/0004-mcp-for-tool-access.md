# ADR-0004: MCP servers for tool access

- **Status:** Accepted
- **Date:** 2026-01-27

## Context
Models and pipelines are owned by different groups and change at different speeds. The
agent needs a stable, typed contract to discover and call them, and the same tools should
be usable from other MCP-capable clients (notebooks, IDE assistants).

## Decision
Expose tools through three domain MCP servers (imaging, genomics, clinical) over
Streamable HTTP. Tool schemas are generated from the shared pydantic registry so the agent
plans against exactly the schema the server validates. Policy is enforced in the agent
gateway, before the call leaves the agent.

## Consequences
- Domains deploy and scale independently; a failing imaging server does not affect clinical.
- One definition per tool; schema drift between client and server is impossible.
- MCP servers are not themselves an authorisation boundary — they are reachable only from
  the API via NetworkPolicy.
