# ADR-0006: Parquet/Delta lake on S3

- **Status:** Accepted
- **Date:** 2026-02-10

## Context
Data volumes are in the terabytes, mostly append-heavy, read by batch analytics and by
tools that need column subsets. We need versioning and reproducibility.

## Decision
Store curated data as Parquet (zstd) on S3 with `<zone>/<modality>/<dataset>/v=<n>/`
layout, with Delta Lake for tables needing ACID upserts. Every publish registers a new
catalog version with a layout-independent content checksum and lineage.

## Consequences
- Cheap storage with lifecycle tiering; columnar reads for tools.
- Analyses can pin a dataset version and verify its checksum.
- Small-file compaction is an operational task handled by a scheduled pipeline.
