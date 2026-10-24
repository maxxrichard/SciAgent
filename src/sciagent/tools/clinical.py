"""Clinical tools: vital-sign anomalies, cohorts, survival and harmonisation."""

from __future__ import annotations

import math
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, Field

from sciagent.data import synthetic
from sciagent.data.harmonise import harmonise_record
from sciagent.tools.registry import Tool

Signal = Literal["heart_rate", "resp_rate", "spo2", "temp_c", "map"]


class VitalAnomaliesInput(BaseModel):
    patient_id: str = Field(..., pattern=r"^PT-\d{5}$")
    signal: Signal = "heart_rate"
    window: int = Field(12, ge=3, le=48, description="Rolling window in hours")
    z_threshold: float = Field(3.0, gt=0, le=10)


def rolling_zscores(x: np.ndarray, window: int) -> np.ndarray:
    """Z-score of each point against the preceding ``window`` points (robust: median/MAD)."""
    z = np.zeros_like(x, dtype=float)
    for i in range(window, len(x)):
        ref = x[i - window : i]
        med = np.median(ref)
        mad = np.median(np.abs(ref - med)) * 1.4826 or 1e-9
        z[i] = (x[i] - med) / mad
    return z


def detect_vital_anomalies(p: VitalAnomaliesInput) -> dict[str, Any]:
    series = synthetic.vitals(p.patient_id, p.signal)
    z = rolling_zscores(series, p.window)
    idx = np.nonzero(np.abs(z) >= p.z_threshold)[0]
    return {
        "patient_id": p.patient_id,
        "signal": p.signal,
        "hours": int(series.size),
        "mean": round(float(series.mean()), 2),
        "anomaly_count": int(idx.size),
        "anomalies": [
            {"hour": int(i), "value": float(series[i]), "z": round(float(z[i]), 2)} for i in idx
        ],
    }


class CohortInput(BaseModel):
    diagnosis: str | None = Field(
        None, description="sepsis, pneumonia, heart_failure, copd, stroke"
    )
    min_age: int = Field(18, ge=0, le=120)
    max_age: int = Field(120, ge=0, le=120)
    sex: Literal["F", "M"] | None = None
    treatment_arm: Literal["treatment", "control"] | None = None
    limit: int = Field(100, ge=1, le=100_000)


def _select(p: CohortInput) -> list[synthetic.Patient]:
    return [
        pt
        for pt in synthetic.clinical_cohort()
        if p.min_age <= pt.age <= p.max_age
        and (p.diagnosis is None or pt.diagnosis == p.diagnosis)
        and (p.sex is None or pt.sex == p.sex)
        and (p.treatment_arm is None or pt.treatment_arm == p.treatment_arm)
    ]


def build_cohort(p: CohortInput) -> dict[str, Any]:
    selected = _select(p)
    ages = np.array([pt.age for pt in selected]) if selected else np.array([0])
    return {
        "criteria": p.model_dump(exclude_none=True),
        "size": len(selected),
        "median_age": float(np.median(ages)) if selected else None,
        "female_fraction": round(sum(pt.sex == "F" for pt in selected) / len(selected), 3)
        if selected
        else None,
        "event_rate": round(sum(pt.event for pt in selected) / len(selected), 3)
        if selected
        else None,
        "patient_ids": [pt.patient_id for pt in selected[: p.limit]],
    }


def kaplan_meier(times: np.ndarray, events: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    order = np.argsort(times)
    times, events = times[order], events[order]
    uniq = np.unique(times[events])
    surv, s = [], 1.0
    for t in uniq:
        at_risk = np.sum(times >= t)
        d = np.sum((times == t) & events)
        s *= 1 - d / at_risk
        surv.append(s)
    return uniq, np.array(surv)


def median_survival(times: np.ndarray, surv: np.ndarray) -> float | None:
    below = np.nonzero(surv <= 0.5)[0]
    return float(times[below[0]]) if below.size else None


def logrank_test(
    t1: np.ndarray, e1: np.ndarray, t2: np.ndarray, e2: np.ndarray
) -> tuple[float, float]:
    """Two-sample log-rank test; returns (chi2, p-value) with 1 degree of freedom."""
    all_t = np.unique(np.concatenate([t1[e1], t2[e2]]))
    o_minus_e, var = 0.0, 0.0
    for t in all_t:
        n1, n2 = np.sum(t1 >= t), np.sum(t2 >= t)
        d1, d2 = np.sum((t1 == t) & e1), np.sum((t2 == t) & e2)
        n, d = n1 + n2, d1 + d2
        if n < 2:
            continue
        o_minus_e += d1 - d * n1 / n
        var += d * (n1 / n) * (n2 / n) * (n - d) / (n - 1)
    chi2 = o_minus_e**2 / var if var > 0 else 0.0
    p = math.erfc(math.sqrt(chi2 / 2))
    return round(float(chi2), 4), float(p)


class SurvivalInput(BaseModel):
    diagnosis: str | None = None
    min_age: int = Field(18, ge=0, le=120)
    max_age: int = Field(120, ge=0, le=120)
    compare_by: Literal["treatment_arm", "sex"] = "treatment_arm"


def survival_analysis(p: SurvivalInput) -> dict[str, Any]:
    cohort = _select(CohortInput(diagnosis=p.diagnosis, min_age=p.min_age, max_age=p.max_age))
    groups: dict[str, list[synthetic.Patient]] = {}
    for pt in cohort:
        groups.setdefault(getattr(pt, p.compare_by), []).append(pt)
    summary: dict[str, Any] = {}
    arrays = {}
    for name, members in sorted(groups.items()):
        t = np.array([m.followup_days for m in members])
        e = np.array([m.event for m in members])
        km_t, km_s = kaplan_meier(t, e)
        arrays[name] = (t, e)
        summary[name] = {
            "n": len(members),
            "events": int(e.sum()),
            "median_survival_days": median_survival(km_t, km_s),
            "survival_at_365d": round(float(km_s[km_t <= 365][-1]), 3)
            if np.any(km_t <= 365)
            else 1.0,
        }
    result: dict[str, Any] = {"compare_by": p.compare_by, "n": len(cohort), "groups": summary}
    if len(arrays) == 2:
        (a_t, a_e), (b_t, b_e) = arrays.values()
        chi2, pval = logrank_test(a_t, a_e, b_t, b_e)
        result["logrank"] = {"chi2": chi2, "p_value": round(pval, 6)}
    return result


class Measurement(BaseModel):
    code: str = Field(..., max_length=32)
    value: float
    unit: str = Field(..., max_length=32)


class HarmoniseInput(BaseModel):
    records: list[Measurement] = Field(..., min_length=1, max_length=5000)


def harmonise_records(p: HarmoniseInput) -> dict[str, Any]:
    out = [harmonise_record(r.code, r.value, r.unit).as_dict() for r in p.records]
    status: dict[str, int] = {}
    for r in out:
        status[r["status"]] = status.get(r["status"], 0) + 1
    return {"records": out, "status_counts": status}


TOOLS = [
    Tool(
        "detect_vital_anomalies",
        "Detect anomalous excursions in a patient's hourly vital-sign time series.",
        "clinical",
        VitalAnomaliesInput,
        detect_vital_anomalies,
    ),
    Tool(
        "build_cohort",
        "Select a patient cohort from the clinical registry by diagnosis, age, sex and arm.",
        "clinical",
        CohortInput,
        build_cohort,
    ),
    Tool(
        "survival_analysis",
        "Kaplan-Meier survival by treatment arm or sex with a log-rank test.",
        "clinical",
        SurvivalInput,
        survival_analysis,
    ),
    Tool(
        "harmonise_records",
        "Map local lab codes to LOINC and convert measurements to canonical units.",
        "clinical",
        HarmoniseInput,
        harmonise_records,
    ),
]
