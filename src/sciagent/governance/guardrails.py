"""Input, tool and output guardrails.

Guardrails are cheap, deterministic checks that run on every agent turn. They are
deliberately conservative: anything blocked is recorded in the audit log and
counted in ``sciagent_guardrail_blocks_total`` so false positives are visible.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from sciagent.core.telemetry import GUARDRAIL_BLOCKS

INJECTION_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"ignore (all |any )?(previous|prior|above) (instructions|prompts)",
        r"disregard (the )?(system|previous) (prompt|instructions)",
        r"(reveal|print|show) (your|the) (system prompt|instructions|policy)",
        r"you are now (in )?(developer|dan|jailbreak) mode",
        r"(bypass|disable|turn off) (the )?(policy|guardrails?|safety|audit)",
        r"act as (an? )?admin",
    )
]
PII_PATTERNS = {
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    # International (+49 ...) or trunk-prefixed (0681 ...) numbers; avoids matching
    # codes like "2160-0 106.1" that appear in harmonised lab output.
    "phone": re.compile(
        r"(?<![\w.\-])(?:\+\d{1,3}[ \-]?|0)\d{2,4}(?:[ \-/]?\d{2,8}){1,4}(?![\w.])"
    ),
    "iban": re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}\b"),
    "date_of_birth": re.compile(
        r"\b(?:dob|born|date of birth)[:\s]+\d{1,4}[./-]\d{1,2}[./-]\d{1,4}", re.I
    ),
}
NUMBER = re.compile(r"(?<![\w.-])-?\d+(?:\.\d+)?(?![\w-])")
MAX_QUESTION_CHARS = 4000


@dataclass
class GuardrailResult:
    allowed: bool
    violations: list[str] = field(default_factory=list)
    text: str = ""


def check_input(question: str) -> GuardrailResult:
    violations: list[str] = []
    if len(question) > MAX_QUESTION_CHARS:
        violations.append("input_too_long")
    if any(p.search(question) for p in INJECTION_PATTERNS):
        violations.append("prompt_injection")
    for name, pattern in PII_PATTERNS.items():
        if pattern.search(question):
            violations.append(f"pii_{name}")
    for v in violations:
        GUARDRAIL_BLOCKS.labels(v, "input").inc()
    return GuardrailResult(not violations, violations, question)


def redact(text: str) -> tuple[str, list[str]]:
    found = []
    for name, pattern in PII_PATTERNS.items():
        if pattern.search(text):
            found.append(name)
            text = pattern.sub(f"[REDACTED:{name}]", text)
    return text, found


def _numbers(text: str) -> set[float]:
    return {round(float(n), 4) for n in NUMBER.findall(text)}


def _collect_numbers(obj: Any, acc: set[float]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, int | float):
        acc.add(round(float(obj), 4))
    elif isinstance(obj, str):
        acc |= _numbers(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect_numbers(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _collect_numbers(v, acc)


def ungrounded_numbers(answer: str, question: str, tool_results: list[Any]) -> set[float]:
    """Numbers in the answer that appear in neither the question nor any tool result.

    Small integers (<= 10) are ignored because they commonly appear as counts or
    ordinals in prose.
    """
    grounded: set[float] = _numbers(question)
    for r in tool_results:
        _collect_numbers(r, grounded)
    return {n for n in _numbers(answer) if abs(n) > 10 and n not in grounded}


def check_output(answer: str, question: str, tool_results: list[Any]) -> GuardrailResult:
    text, pii = redact(answer)
    violations = [f"pii_{p}" for p in pii]
    if tool_results:
        missing = ungrounded_numbers(text, question, tool_results)
        if missing:
            violations.append("ungrounded_numbers")
            text += "\n\n⚠️ Some figures could not be traced to tool outputs: " + ", ".join(
                sorted(json.dumps(n) for n in missing)
            )
    for v in violations:
        GUARDRAIL_BLOCKS.labels(v, "output").inc()
    # PII is redacted rather than blocked; ungrounded numbers are flagged, not hidden.
    return GuardrailResult(True, violations, text)
