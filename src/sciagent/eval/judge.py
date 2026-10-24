"""LLM-as-judge.

``HeuristicJudge`` is deterministic and used in CI; ``LLMJudge`` asks the served
model to grade the answer against the task rubric and returns a 1-5 score. Both
return a :class:`Verdict`; low or disputed scores are routed to human review.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol

from sciagent.eval.tasks import EvalTask
from sciagent.llm.base import LLMClient

JUDGE_PROMPT = """You are grading an AI research assistant's answer.
Question: {question}
Rubric: {rubric}
Answer: {answer}
Tool outputs (ground truth): {evidence}

Score 1-5 where 5 = correct, complete, grounded in tool outputs and appropriately
caveated; 1 = wrong or unsafe. Reply with JSON only: {{"score": <int>, "reason": "<short>"}}"""


@dataclass(frozen=True)
class Verdict:
    score: int
    reason: str
    judge: str


class Judge(Protocol):
    name: str

    def grade(self, task: EvalTask, answer: str, evidence: list[dict[str, object]]) -> Verdict: ...


RUBRIC_STOPWORDS = frozenset(
    [
        "reports",
        "explains",
        "answer",
        "answers",
        "with",
        "without",
        "from",
        "that",
        "this",
        "their",
        "the",
        "and",
        "for",
        "per",
        "into",
        "each",
        "when",
        "where",
        "which",
        "appropriately",
        "accurate",
    ]
)


class HeuristicJudge:
    """Scores rubric coverage using 5-character stems, penalising ungrounded figures."""

    name = "heuristic"

    def grade(self, task: EvalTask, answer: str, evidence: list[dict[str, object]]) -> Verdict:
        if not answer.strip():
            return Verdict(1, "empty answer", self.name)
        terms = {
            t[:5]
            for t in re.findall(r"[a-z][a-z0-9\-]{3,}", task.rubric.lower())
            if t not in RUBRIC_STOPWORDS
        }
        stems = {w[:5] for w in re.findall(r"[a-z][a-z0-9\-]{3,}", answer.lower())}
        coverage = len(terms & stems) / len(terms) if terms else 1.0
        flagged = "could not be traced" in answer
        score = 1 + round(4 * coverage) - (2 if flagged else 0)
        score = max(1, min(5, score))
        return Verdict(
            score, f"rubric coverage {coverage:.2f}{', ungrounded' if flagged else ''}", self.name
        )


class LLMJudge:
    name = "llm"

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def grade(self, task: EvalTask, answer: str, evidence: list[dict[str, object]]) -> Verdict:
        prompt = JUDGE_PROMPT.format(
            question=task.question,
            rubric=task.rubric or "Answer is accurate and grounded.",
            answer=answer,
            evidence=json.dumps(evidence, default=str)[:6000],
        )
        resp = self.llm.chat([{"role": "user", "content": prompt}], [])
        try:
            raw = re.search(r"\{.*\}", resp.content or "", re.S)
            data = json.loads(raw.group(0) if raw else "")
            return Verdict(
                max(1, min(5, int(data["score"]))), str(data.get("reason", "")), self.name
            )
        except (ValueError, KeyError, TypeError):
            return Verdict(1, "unparseable judge output", self.name)
