"""Genomics tools: variant annotation summary and single-cell expression QC."""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
from pydantic import BaseModel, Field

from sciagent.data import synthetic
from sciagent.tools.registry import Tool

TRANSITIONS = {("A", "G"), ("G", "A"), ("C", "T"), ("T", "C")}


class AnnotateVariantsInput(BaseModel):
    sample_id: str = Field(..., pattern=r"^WGS-\d{4}$", description="Sequencing sample, WGS-0001")
    genes: list[str] | None = Field(None, description="Restrict to a gene panel")
    min_impact: str = Field("LOW", pattern=r"^(MODIFIER|LOW|MODERATE|HIGH)$")
    limit: int = Field(1000, ge=1, le=100_000)


_IMPACT_RANK = {"MODIFIER": 0, "LOW": 1, "MODERATE": 2, "HIGH": 3}


def annotate_variants(p: AnnotateVariantsInput) -> dict[str, Any]:
    variants = synthetic.variants(p.sample_id)[: p.limit]
    if p.genes:
        wanted = {g.upper() for g in p.genes}
        variants = [v for v in variants if v.gene in wanted]
    floor = _IMPACT_RANK[p.min_impact]
    kept = [v for v in variants if _IMPACT_RANK[v.impact] >= floor]
    ts = sum((v.ref, v.alt) in TRANSITIONS for v in kept)
    tv = len(kept) - ts
    high = sorted(
        (v for v in kept if v.impact == "HIGH"), key=lambda v: v.allele_freq, reverse=True
    )
    return {
        "sample_id": p.sample_id,
        "variants_considered": len(variants),
        "variants_passing": len(kept),
        "by_impact": dict(Counter(v.impact for v in kept)),
        "by_gene": dict(Counter(v.gene for v in kept).most_common(5)),
        "ts_tv_ratio": round(ts / tv, 3) if tv else None,
        "top_high_impact": [
            {
                "gene": v.gene,
                "variant": f"{v.chrom}:{v.pos}{v.ref}>{v.alt}",
                "consequence": v.consequence,
                "af": v.allele_freq,
            }
            for v in high[:5]
        ],
    }


class ExpressionQCInput(BaseModel):
    sample_id: str = Field(..., pattern=r"^SC-\d{4}$", description="Single-cell library, SC-0001")
    min_genes: int = Field(200, ge=0)
    max_mito_fraction: float = Field(0.2, gt=0, le=1)


def expression_qc(p: ExpressionQCInput) -> dict[str, Any]:
    counts, is_mito = synthetic.expression_matrix(p.sample_id)
    total = counts.sum(axis=1)
    n_genes = (counts > 0).sum(axis=1)
    mito = np.divide(
        counts[:, is_mito].sum(axis=1),
        total,
        where=total > 0,
        out=np.zeros_like(total, dtype=float),
    )
    passing = (n_genes >= p.min_genes) & (mito <= p.max_mito_fraction)
    return {
        "sample_id": p.sample_id,
        "cells": int(counts.shape[0]),
        "genes": int(counts.shape[1]),
        "median_umis_per_cell": float(np.median(total)),
        "median_genes_per_cell": float(np.median(n_genes)),
        "median_mito_fraction": round(float(np.median(mito)), 4),
        "cells_passing_qc": int(passing.sum()),
        "pass_rate": round(float(passing.mean()), 4),
    }


TOOLS = [
    Tool(
        "annotate_variants",
        "Summarise annotated variants for a sequencing sample (impact, genes, Ts/Tv).",
        "genomics",
        AnnotateVariantsInput,
        annotate_variants,
    ),
    Tool(
        "expression_qc",
        "Run single-cell RNA-seq quality control (UMIs, genes, mitochondrial fraction).",
        "genomics",
        ExpressionQCInput,
        expression_qc,
    ),
]
