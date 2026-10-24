"""Deterministic planner used for local development, CI and as an offline fallback.

It speaks the same message protocol as the vLLM client: given a conversation it
either emits tool calls (when no tool results are present yet) or a final answer
composed from the tool results. Behaviour is fully reproducible, which makes it
the reference agent for the evaluation harness's regression suite.
"""

from __future__ import annotations

import json
import re
from typing import Any

from sciagent.data.synthetic import DIAGNOSES, GENE_PANEL
from sciagent.llm.base import LLMResponse, Message, ToolCall, Usage

IDS = {
    "image": re.compile(r"\bIMG-\d{4}\b"),
    "wgs": re.compile(r"\bWGS-\d{4}\b"),
    "sc": re.compile(r"\bSC-\d{4}\b"),
    "patient": re.compile(r"\bPT-\d{5}\b"),
}
SIGNALS = {
    "heart_rate": ("heart rate", "pulse", "hr "),
    "resp_rate": ("respiratory", "breathing", "resp rate"),
    "spo2": ("spo2", "oxygen", "saturation"),
    "temp_c": ("temperature", "fever"),
    "map": ("blood pressure", "map", "arterial"),
}
MEASUREMENT = re.compile(
    r"\b([A-Z]{2,5})\s*[=:]?\s*(-?\d+(?:\.\d+)?)\s*([A-Za-z°µ/\[\]_]+(?:/[A-Za-z]+)?)"
)
AGE_RANGE = re.compile(r"aged?\s+(\d{1,3})\s*(?:-|to|\u2013)\s*(\d{1,3})")
AGE_OVER = re.compile(r"(?:over|older than|above|>)\s*(\d{1,3})")
AGE_UNDER = re.compile(r"(?:under|younger than|below|<)\s*(\d{1,3})")


def _tokens(text: str) -> int:
    return max(1, int(len(text.split()) * 1.3))


class RuleBasedLLM:
    model = "rule-based-planner"

    def chat(self, messages: list[Message], tools: list[dict[str, Any]]) -> LLMResponse:
        prompt_tokens = sum(_tokens(str(m.get("content") or "")) for m in messages)
        question = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        tool_msgs = [m for m in messages if m["role"] == "tool"]
        available = {t["name"] for t in tools}
        if not tool_msgs:
            calls = [c for c in self.plan(question) if c.name in available]
            if calls:
                return LLMResponse(None, calls, Usage(prompt_tokens, 20 * len(calls)))
            answer = (
                "I could not map this question to an available analysis. I can segment "
                "microscopy images (IMG-####), summarise variants (WGS-####), run single-cell "
                "QC (SC-####), check vital signs (PT-#####), build cohorts, run survival "
                "analyses and harmonise lab records."
            )
            return LLMResponse(answer, [], Usage(prompt_tokens, _tokens(answer)))
        answer = self.summarise(tool_msgs)
        return LLMResponse(answer, [], Usage(prompt_tokens, _tokens(answer)))

    # ------------------------------------------------------------------ planning
    def plan(self, question: str) -> list[ToolCall]:
        q = question.lower()
        calls: list[dict[str, Any]] = []

        for img in IDS["image"].findall(question):
            if any(k in q for k in ("feature", "intensity", "texture", "snr", "signal-to-noise")):
                calls.append({"name": "extract_image_features", "arguments": {"sample_id": img}})
            if any(k in q for k in ("segment", "cell", "nuclei", "count")) or not any(
                c["arguments"].get("sample_id") == img for c in calls
            ):
                calls.append({"name": "segment_cells", "arguments": {"sample_id": img}})

        for wgs in IDS["wgs"].findall(question):
            args: dict[str, Any] = {"sample_id": wgs}
            genes = [g for g in GENE_PANEL if re.search(rf"\b{g.lower()}\b", q)]
            if genes:
                args["genes"] = genes
            for level in ("high", "moderate"):
                if f"{level} impact" in q or f"{level}-impact" in q:
                    args["min_impact"] = level.upper()
                    break
            calls.append({"name": "annotate_variants", "arguments": args})

        for sc in IDS["sc"].findall(question):
            calls.append({"name": "expression_qc", "arguments": {"sample_id": sc}})

        for pt in IDS["patient"].findall(question):
            signals = [s for s, keys in SIGNALS.items() if any(k in q + " " for k in keys)]
            for signal in signals or ["heart_rate"]:
                calls.append(
                    {
                        "name": "detect_vital_anomalies",
                        "arguments": {"patient_id": pt, "signal": signal},
                    }
                )

        criteria = self._criteria(q)
        if any(k in q for k in ("survival", "kaplan", "log-rank", "logrank", "mortality")):
            args = {k: v for k, v in criteria.items() if k in ("diagnosis", "min_age", "max_age")}
            if re.search(r"\b(sex|gender|female|male)\b", q):
                args["compare_by"] = "sex"
            calls.append({"name": "survival_analysis", "arguments": args})
        elif "cohort" in q or re.search(r"how many (patients|subjects)", q):
            calls.append({"name": "build_cohort", "arguments": criteria})

        if any(k in q for k in ("harmonis", "harmoniz", "loinc", "convert", "canonical unit")):
            records = [
                {"code": c, "value": float(v), "unit": u}
                for c, v, u in MEASUREMENT.findall(question)
                if c not in {"IMG", "WGS", "SC", "PT"}
            ]
            if records:
                calls.append({"name": "harmonise_records", "arguments": {"records": records}})

        return [
            ToolCall(id=f"call_{i}", name=c["name"], arguments=c["arguments"])
            for i, c in enumerate(calls)
        ]

    @staticmethod
    def _criteria(q: str) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for dx in DIAGNOSES:
            if dx.replace("_", " ") in q or dx in q:
                out["diagnosis"] = dx
        if m := AGE_RANGE.search(q):
            out["min_age"], out["max_age"] = int(m.group(1)), int(m.group(2))
        else:
            if m := AGE_OVER.search(q):
                out["min_age"] = int(m.group(1)) + 1
            if m := AGE_UNDER.search(q):
                out["max_age"] = int(m.group(1)) - 1
        if re.search(r"\b(women|female)\b", q):
            out["sex"] = "F"
        elif re.search(r"\b(men|male)\b", q):
            out["sex"] = "M"
        if "control arm" in q or "control group" in q:
            out["treatment_arm"] = "control"
        elif "treatment arm" in q or "treated" in q:
            out["treatment_arm"] = "treatment"
        return out

    # --------------------------------------------------------------- summarising
    def summarise(self, tool_msgs: list[Message]) -> str:
        parts = []
        for m in tool_msgs:
            name = m.get("name", "tool")
            payload = json.loads(m["content"])
            if "error" in payload:
                err = str(payload["error"])
                if err.startswith("denied: "):
                    parts.append(f"Access to {name} was denied by policy: {err[8:]}.")
                else:
                    parts.append(f"{name} could not be run: {err}.")
                continue
            fmt = getattr(self, f"_fmt_{name}", None)
            parts.append(fmt(payload) if fmt else f"{name}: {json.dumps(payload)[:300]}")
        return " ".join(parts)

    @staticmethod
    def _fmt_segment_cells(r: dict[str, Any]) -> str:
        return (
            f"{r['sample_id']}: segmented {r['cell_count']} nuclei (Otsu threshold "
            f"{r['threshold']}), mean area {r['mean_area_px']} px."
        )

    @staticmethod
    def _fmt_extract_image_features(r: dict[str, Any]) -> str:
        return (
            f"{r['sample_id']}: mean intensity {r['mean_intensity']}, foreground fraction "
            f"{r['foreground_fraction']}, SNR {r['snr_db']} dB."
        )

    @staticmethod
    def _fmt_annotate_variants(r: dict[str, Any]) -> str:
        impact = ", ".join(f"{k} {v}" for k, v in sorted(r["by_impact"].items()))
        top = r["top_high_impact"][0] if r["top_high_impact"] else None
        lead = f" Top high-impact: {top['gene']} {top['consequence']}." if top else ""
        return (
            f"{r['sample_id']}: {r['variants_passing']} of {r['variants_considered']} variants "
            f"pass the filter ({impact}); Ts/Tv {r['ts_tv_ratio']}.{lead}"
        )

    @staticmethod
    def _fmt_expression_qc(r: dict[str, Any]) -> str:
        return (
            f"{r['sample_id']}: {r['cells_passing_qc']} of {r['cells']} cells pass QC "
            f"(pass rate {r['pass_rate']}); median {r['median_genes_per_cell']} genes per cell."
        )

    @staticmethod
    def _fmt_detect_vital_anomalies(r: dict[str, Any]) -> str:
        hours = ", ".join(str(a["hour"]) for a in r["anomalies"]) or "none"
        return (
            f"{r['patient_id']} {r['signal']}: {r['anomaly_count']} anomalies over "
            f"{r['hours']} h (hours {hours}); mean {r['mean']}."
        )

    @staticmethod
    def _fmt_build_cohort(r: dict[str, Any]) -> str:
        return (
            f"Cohort of {r['size']} patients (median age {r['median_age']}, female fraction "
            f"{r['female_fraction']}, event rate {r['event_rate']})."
        )

    @staticmethod
    def _fmt_survival_analysis(r: dict[str, Any]) -> str:
        groups = "; ".join(
            f"{name}: n={g['n']}, median survival {g['median_survival_days']} days"
            for name, g in r["groups"].items()
        )
        lr = r.get("logrank")
        test = f" Log-rank p={lr['p_value']}." if lr else ""
        return f"Survival by {r['compare_by']} ({groups}).{test}"

    @staticmethod
    def _fmt_harmonise_records(r: dict[str, Any]) -> str:
        ok = [x for x in r["records"] if x["status"] == "ok"]
        mapped = "; ".join(
            f"{x['source_code']} → LOINC {x['loinc']} ({x['display']}), {x['value']} {x['unit']}"
            for x in ok
        )
        return (
            f"Harmonised {len(ok)} of {len(r['records'])} records to LOINC codes with "
            f"canonical units: {mapped}."
        )
