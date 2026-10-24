"""Data-lake I/O for the raw and curated zones.

Tables are written as Parquet (default) or Delta Lake when the optional
``deltalake`` dependency is installed. Paths follow
``<root>/<zone>/<modality>/<dataset>/v=<version>/``; with an ``s3://`` root the
same layout is used on S3 through ``pyarrow.fs``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pyarrow as pa
import pyarrow.parquet as pq

Zone = Literal["raw", "curated", "artifacts"]


@dataclass(frozen=True)
class WriteResult:
    uri: str
    rows: int
    checksum: str
    schema: dict[str, str]


def table_checksum(table: pa.Table) -> str:
    """Content hash independent of file layout, used for reproducibility checks."""
    h = hashlib.sha256()
    h.update(json.dumps([(f.name, str(f.type)) for f in table.schema]).encode())
    # Re-batch to a fixed size so the hash does not depend on how the table is chunked.
    for batch in table.combine_chunks().to_batches(max_chunksize=65_536):
        h.update(json.dumps(batch.to_pylist(), sort_keys=True, default=str).encode())
    return h.hexdigest()


class Lake:
    def __init__(self, root: str, fmt: Literal["parquet", "delta"] = "parquet") -> None:
        self.root = root.rstrip("/")
        self.fmt = fmt

    def path(self, zone: Zone, modality: str, dataset: str, version: int) -> str:
        return f"{self.root}/{zone}/{modality}/{dataset}/v={version}"

    def write(
        self, rows: list[dict[str, Any]], *, zone: Zone, modality: str, dataset: str, version: int
    ) -> WriteResult:
        table = pa.Table.from_pylist(rows)
        target = self.path(zone, modality, dataset, version)
        if self.fmt == "delta":  # pragma: no cover - optional dependency
            from deltalake import write_deltalake

            write_deltalake(target, table, mode="overwrite")
        else:
            if "://" not in target:
                Path(target).mkdir(parents=True, exist_ok=True)
            pq.write_table(table, f"{target}/part-00000.parquet", compression="zstd")
        return WriteResult(
            uri=target,
            rows=table.num_rows,
            checksum=table_checksum(table),
            schema={f.name: str(f.type) for f in table.schema},
        )

    def read(self, uri: str) -> pa.Table:
        return pq.read_table(uri)
