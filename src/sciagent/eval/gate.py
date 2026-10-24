"""Release gate: compare an evaluation summary against thresholds."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_gate(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text())["thresholds"]


def evaluate_gate(summary: dict[str, Any], thresholds: dict[str, Any]) -> list[str]:
    """Return violated thresholds; an empty list means the release may proceed."""
    problems: list[str] = []
    if summary["pass_rate"] < thresholds.get("min_pass_rate", 0):
        problems.append(f"pass_rate {summary['pass_rate']} < {thresholds['min_pass_rate']}")
    for cat, floor in thresholds.get("min_category_pass_rate", {}).items():
        got = summary["by_category"].get(cat)
        if got is None:
            problems.append(f"category '{cat}' has no tasks")
        elif got < floor:
            problems.append(f"{cat} pass_rate {got} < {floor}")
    for check, floor in thresholds.get("min_check_rate", {}).items():
        got = summary["check_rates"].get(check, 0.0)
        if got < floor:
            problems.append(f"{check} rate {got} < {floor}")
    if summary["judge_mean"] < thresholds.get("min_judge_mean", 0):
        problems.append(f"judge_mean {summary['judge_mean']} < {thresholds['min_judge_mean']}")
    if (cap := thresholds.get("max_latency_p95_s")) and summary["latency_p95_s"] > cap:
        problems.append(f"latency_p95_s {summary['latency_p95_s']} > {cap}")
    return problems
