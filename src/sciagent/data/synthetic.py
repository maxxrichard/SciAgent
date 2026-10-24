"""Deterministic synthetic data for local development, tests and demos.

Every generator is a pure function of its identifier, so ``sample_id="IMG-0007"``
always yields the same image. Real deployments resolve identifiers against the
curated zone of the data lake instead (see :mod:`sciagent.data.lake`).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np

GENE_PANEL = (
    "TP53",
    "BRCA1",
    "BRCA2",
    "EGFR",
    "KRAS",
    "PIK3CA",
    "APC",
    "PTEN",
    "MYC",
    "ALK",
)
CONSEQUENCES = (
    ("missense_variant", "MODERATE"),
    ("synonymous_variant", "LOW"),
    ("stop_gained", "HIGH"),
    ("frameshift_variant", "HIGH"),
    ("splice_region_variant", "LOW"),
    ("intron_variant", "MODIFIER"),
    ("inframe_deletion", "MODERATE"),
)
DIAGNOSES = ("sepsis", "pneumonia", "heart_failure", "copd", "stroke")


def _rng(key: str) -> np.random.Generator:
    seed = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big")
    return np.random.default_rng(seed)


def microscopy_image(sample_id: str, size: int = 64) -> np.ndarray:
    """Fluorescence-like image with a handful of bright, roughly round nuclei."""
    rng = _rng(f"img:{sample_id}")
    img = rng.normal(0.08, 0.02, (size, size))
    yy, xx = np.mgrid[0:size, 0:size]
    n_cells = int(rng.integers(6, 16))
    for _ in range(n_cells):
        cy, cx = rng.integers(5, size - 5, 2)
        r = rng.uniform(2.0, 4.5)
        mask = (yy - cy) ** 2 + (xx - cx) ** 2 <= r**2
        img[mask] += rng.uniform(0.5, 0.9)
    return np.clip(img, 0.0, 1.0)


@dataclass(frozen=True)
class Variant:
    chrom: str
    pos: int
    ref: str
    alt: str
    gene: str
    consequence: str
    impact: str
    allele_freq: float


def variants(sample_id: str, n: int = 120) -> list[Variant]:
    rng = _rng(f"vcf:{sample_id}")
    bases = np.array(list("ACGT"))
    out: list[Variant] = []
    for _ in range(n):
        ref, alt = rng.choice(bases, 2, replace=False)
        cons, impact = CONSEQUENCES[int(rng.integers(0, len(CONSEQUENCES)))]
        out.append(
            Variant(
                chrom=f"chr{int(rng.integers(1, 23))}",
                pos=int(rng.integers(1_000, 250_000_000)),
                ref=str(ref),
                alt=str(alt),
                gene=GENE_PANEL[int(rng.integers(0, len(GENE_PANEL)))],
                consequence=cons,
                impact=impact,
                allele_freq=float(np.round(rng.beta(2, 5), 4)),
            )
        )
    return out


def expression_matrix(
    sample_id: str, cells: int = 400, genes: int = 2000
) -> tuple[np.ndarray, np.ndarray]:
    """Return (counts[cells, genes], is_mito[genes]) with a few low-quality cells."""
    rng = _rng(f"scrna:{sample_id}")
    depth = rng.lognormal(7.5, 0.6, cells)
    probs = rng.dirichlet(np.full(genes, 0.05))
    counts = rng.poisson(np.outer(depth, probs))
    is_mito = np.zeros(genes, dtype=bool)
    is_mito[:13] = True
    damaged = rng.choice(cells, size=cells // 12, replace=False)
    counts[np.ix_(damaged, np.arange(13))] += rng.poisson(40, (damaged.size, 13))
    return counts, is_mito


def vitals(patient_id: str, signal: str = "heart_rate", hours: int = 72) -> np.ndarray:
    """Hourly vital-sign series with injected physiological excursions."""
    rng = _rng(f"vitals:{patient_id}:{signal}")
    base = {"heart_rate": 78, "resp_rate": 16, "spo2": 97, "temp_c": 36.9, "map": 85}[signal]
    noise = {"heart_rate": 4, "resp_rate": 1.5, "spo2": 0.8, "temp_c": 0.2, "map": 5}[signal]
    t = np.arange(hours)
    series = base + noise * rng.standard_normal(hours) + 0.3 * noise * np.sin(t / 24 * 2 * np.pi)
    for idx in rng.choice(np.arange(6, hours), size=int(rng.integers(1, 4)), replace=False):
        series[idx] += noise * rng.choice([-1, 1]) * rng.uniform(5, 8)
    return np.round(series, 2)


@dataclass(frozen=True)
class Patient:
    patient_id: str
    age: int
    sex: str
    diagnosis: str
    treatment_arm: str
    followup_days: float
    event: bool


def clinical_cohort(n: int = 500, seed: str = "registry-v1") -> list[Patient]:
    rng = _rng(f"cohort:{seed}")
    patients = []
    for i in range(n):
        arm = "treatment" if rng.random() < 0.5 else "control"
        hazard = 1 / (420 if arm == "treatment" else 300)
        t_event = rng.exponential(1 / hazard)
        t_censor = rng.uniform(90, 730)
        patients.append(
            Patient(
                patient_id=f"PT-{i:05d}",
                age=int(np.clip(rng.normal(64, 12), 18, 95)),
                sex="F" if rng.random() < 0.48 else "M",
                diagnosis=DIAGNOSES[int(rng.integers(0, len(DIAGNOSES)))],
                treatment_arm=arm,
                followup_days=float(round(min(t_event, t_censor), 1)),
                event=bool(t_event <= t_censor),
            )
        )
    return patients
