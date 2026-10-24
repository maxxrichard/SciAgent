# Getting started

## Prerequisites

- Python 3.11 or 3.12 and [uv](https://docs.astral.sh/uv/) (pip works too)
- Docker (optional) for the full local stack

## Install and verify

```bash
make install   # .venv with sciagent[dev,docs]
make lint typecheck test
make eval      # curated evaluation suite against evals/gate.yaml
```

## Ask questions locally

```bash
.venv/bin/sciagent query "Summarise the high impact variants for WGS-0002"
.venv/bin/sciagent query "Does survival differ by sex in pneumonia patients?" --json
```

Use `--api-key dev-admin-key` to act as an administrator. Keys and their groups are
configured with `SCIAGENT_API_KEYS` (see `.env.example`).

## Populate the catalog

```bash
.venv/bin/sciagent pipelines list
.venv/bin/sciagent pipelines run all     # 40 pipelines → .lake/curated/... + catalog rows
```

## Run services

```bash
make run    # API on :8000 with in-process tools
make mcp    # the three MCP servers on :8101-8103
SCIAGENT_TOOL_TRANSPORT=mcp make run   # API calling tools over MCP
```

Or everything at once: `docker compose up --build`.
