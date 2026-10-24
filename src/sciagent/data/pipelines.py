"""Pipeline specs and an engine-agnostic runner.

A pipeline is ``extract → validate → publish → register``. The same
:func:`run_pipeline` call is used by Airflow tasks, the CLI and tests, so what
runs in production is exactly what is tested.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from sciagent.catalog.repository import DatasetRepository
from sciagent.core.errors import NotFoundError, ValidationFailed
from sciagent.core.telemetry import PIPELINE_FAILURES
from sciagent.data import synthetic
from sciagent.data.harmonise import harmonise_record
from sciagent.data.lake import Lake
from sciagent.tools import clinical, genomics, imaging

SPEC_FILE = Path(__file__).with_name("pipelines.yaml")

Rows = list[dict[str, Any]]


@dataclass(frozen=True)
class PipelineSpec:
    id: str
    kind: str
    modality: str
    group: str
    schedule: str
    params: dict[str, Any]
    checks: dict[str, Any]
    description: str


@dataclass
class PipelineResult:
    pipeline: str
    dataset_id: str
    version: int
    rows: int
    uri: str
    checksum: str
    timings_s: dict[str, float] = field(default_factory=dict)


def load_specs(path: Path = SPEC_FILE) -> list[PipelineSpec]:
    raw = yaml.safe_load(path.read_text())
    return [PipelineSpec(**p) for p in raw["pipelines"]]


def get_spec(pipeline_id: str, specs: list[PipelineSpec] | None = None) -> PipelineSpec:
    for spec in specs or load_specs():
        if spec.id == pipeline_id:
            return spec
    raise NotFoundError("unknown pipeline", pipeline=pipeline_id)


# ------------------------------------------------------------------ extractors
def _imaging_segmentation(p: dict[str, Any]) -> Rows:
    return [
        imaging.segment_cells(imaging.SegmentCellsInput(sample_id=s)) | {"site": p["site"]}
        for s in p["samples"]
    ]


def _imaging_features(p: dict[str, Any]) -> Rows:
    return [
        imaging.extract_image_features(imaging.ImageFeaturesInput(sample_id=s))
        | {"site": p["site"]}
        for s in p["samples"]
    ]


def _genomics_variants(p: dict[str, Any]) -> Rows:
    return [
        {"sample_id": s, "site": p["site"], **v.__dict__}
        for s in p["samples"]
        for v in synthetic.variants(s)
    ]


def _scrna_qc(p: dict[str, Any]) -> Rows:
    return [
        genomics.expression_qc(genomics.ExpressionQCInput(sample_id=s)) | {"site": p["site"]}
        for s in p["samples"]
    ]


def _clinical_vitals(p: dict[str, Any]) -> Rows:
    offset = {"site-a": 0, "site-b": 1000, "site-c": 2000}.get(p["site"], 3000)
    rows: Rows = []
    for i in range(p["patients"]):
        pid = f"PT-{offset + i:05d}"
        series = synthetic.vitals(pid, p["signal"])
        z = clinical.rolling_zscores(series, 12)
        rows += [
            {
                "patient_id": pid,
                "site": p["site"],
                "signal": p["signal"],
                "hour": h,
                "value": float(v),
                "robust_z": round(float(z[h]), 3),
            }
            for h, v in enumerate(series)
        ]
    return rows


# "NA" (sodium) is intentionally absent from LOCAL_TO_LOINC to exercise the unmapped path.
_LAB_FEED = [
    ("TEMP", 98.4, "F"),
    ("BT", 37.2, "C"),
    ("GLU", 104, "mg/dL"),
    ("GLUC", 5.6, "mmol/L"),
    ("CREA", 0.9, "mg/dL"),
    ("WT", 172, "lb"),
    ("HT", 1.74, "m"),
    ("HR", 71, "bpm"),
    ("HGB", 135, "g/L"),
    ("NA", 140, "mmol/L"),
]


def _lab_harmonisation(p: dict[str, Any]) -> Rows:
    rows: Rows = []
    for i in range(p["records"]):
        code, value, unit = _LAB_FEED[i % len(_LAB_FEED)]
        rec = harmonise_record(code, value * (1 + 0.01 * (i % 7)), unit)
        if rec.status == "ok":
            rows.append({"record_id": f"{p['site']}-{i:06d}", "site": p["site"], **rec.as_dict()})
    return rows


def _clinical_registry(p: dict[str, Any]) -> Rows:
    return [
        pt.__dict__.copy()
        for pt in synthetic.clinical_cohort()
        if p.get("diagnosis") in (None, pt.diagnosis)
    ]


EXTRACTORS: dict[str, Callable[[dict[str, Any]], Rows]] = {
    "imaging_segmentation": _imaging_segmentation,
    "imaging_features": _imaging_features,
    "genomics_variants": _genomics_variants,
    "scrna_qc": _scrna_qc,
    "clinical_vitals": _clinical_vitals,
    "lab_harmonisation": _lab_harmonisation,
    "clinical_registry": _clinical_registry,
}


# ------------------------------------------------------------------ validation
def validate(rows: Rows, checks: dict[str, Any]) -> list[str]:
    """Return a list of human-readable check failures (empty means pass)."""
    failures: list[str] = []
    if len(rows) < checks.get("min_rows", 0):
        failures.append(f"expected at least {checks['min_rows']} rows, got {len(rows)}")
    for col in checks.get("not_null", []):
        nulls = sum(r.get(col) is None for r in rows)
        if nulls:
            failures.append(f"{col}: {nulls} null values")
    for col, (lo, hi) in checks.get("range", {}).items():
        bad = [r[col] for r in rows if r.get(col) is not None and not lo <= r[col] <= hi]
        if bad:
            failures.append(f"{col}: {len(bad)} values outside [{lo}, {hi}]")
    if unique := checks.get("unique"):
        keys = [tuple(r.get(c) for c in unique) for r in rows]
        if len(keys) != len(set(keys)):
            failures.append(f"{'+'.join(unique)}: {len(keys) - len(set(keys))} duplicate keys")
    return failures


# ---------------------------------------------------------------------- runner
def run_pipeline(spec: PipelineSpec, lake: Lake, datasets: DatasetRepository) -> PipelineResult:
    timings: dict[str, float] = {}
    try:
        t = time.perf_counter()
        rows = EXTRACTORS[spec.kind](spec.params)
        timings["extract"] = time.perf_counter() - t

        t = time.perf_counter()
        failures = validate(rows, spec.checks)
        timings["validate"] = time.perf_counter() - t
        if failures:
            raise ValidationFailed(
                "data quality checks failed", pipeline=spec.id, failures=failures
            )

        try:
            version = datasets.latest(spec.id).version + 1
        except NotFoundError:
            version = 1
        t = time.perf_counter()
        written = lake.write(
            rows, zone="curated", modality=spec.modality, dataset=spec.id, version=version
        )
        timings["publish"] = time.perf_counter() - t

        ds = datasets.register(
            name=spec.id,
            modality=spec.modality,
            group=spec.group,
            uri=written.uri,
            row_count=written.rows,
            checksum=written.checksum,
            schema=written.schema,
            lineage={"pipeline": spec.id, "kind": spec.kind, "params": spec.params},
            description=spec.description,
        )
    except Exception:
        PIPELINE_FAILURES.labels(spec.id).inc()
        raise
    return PipelineResult(
        pipeline=spec.id,
        dataset_id=ds.id,
        version=ds.version,
        rows=written.rows,
        uri=written.uri,
        checksum=written.checksum,
        timings_s={k: round(v, 4) for k, v in timings.items()},
    )
