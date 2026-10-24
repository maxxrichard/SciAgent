# Data layer

## Zones

| Zone | Contents | Writers | Readers |
|---|---|---|---|
| `raw` | Landed source extracts, immutable | ingestion | Airflow |
| `curated` | Validated, harmonised Parquet/Delta tables, versioned `v=<n>` | Airflow | API, MCP servers |
| `artifacts` | Evaluation reports, model outputs | API, CI | everyone (read) |

## Pipelines

`src/sciagent/data/pipelines.yaml` declares 40 pipelines across imaging (segmentation,
features), genomics (variants, scRNA QC), clinical vitals (5 signals × 3 sites), lab
harmonisation and outcome registry snapshots. Each has a schedule and quality checks.

```
extract → validate (min_rows, not_null, range, unique) → publish (lake) → register (catalog)
```

The runner is engine-agnostic: the Airflow DAG factory in `dags/` wraps the same
`run_pipeline` call used by the CLI and the tests.

## Reproducibility

- Every publish creates a new dataset **version** with a **content checksum** that is
  independent of file layout, plus lineage (pipeline, kind, parameters).
- Re-running a pipeline on unchanged inputs yields the same checksum; tests assert this.

## Harmonisation

`sciagent/data/harmonise.py` maps site-local lab codes to LOINC and converts to canonical
UCUM units (e.g. °F → Cel, mg/dL → mmol/L for glucose). Unmapped or unconvertible records
are kept with an explicit status rather than silently dropped.
