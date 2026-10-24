"""Run evaluation tasks against an agent and score them."""

from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from sciagent.agent import SciAgent
from sciagent.core.ids import new_id
from sciagent.core.security import Principal
from sciagent.eval.judge import HeuristicJudge, Judge, Verdict
from sciagent.eval.tasks import EvalTask
from sciagent.tools.registry import ToolRegistry


def dig(obj: Any, path: str) -> Any:
    for key in path.split("."):
        obj = obj[int(key)] if isinstance(obj, list) else obj[key]
    return obj


@dataclass
class TaskResult:
    task_id: str
    category: str
    passed: bool
    checks: dict[str, bool]
    status: str
    answer: str
    tools_called: list[str]
    latency_s: float
    tokens: int
    verdict: Verdict
    needs_review: bool = False
    failures: list[str] = field(default_factory=list)


@dataclass
class EvalReport:
    results: list[TaskResult]

    @property
    def summary(self) -> dict[str, Any]:
        by_cat: dict[str, list[TaskResult]] = defaultdict(list)
        for r in self.results:
            by_cat[r.category].append(r)
        latencies = sorted(r.latency_s for r in self.results) or [0.0]
        check_names = {c for r in self.results for c in r.checks}
        return {
            "tasks": len(self.results),
            "pass_rate": _rate(self.results),
            "by_category": {c: _rate(rs) for c, rs in sorted(by_cat.items())},
            "check_rates": {
                c: round(
                    sum(r.checks[c] for r in self.results if c in r.checks)
                    / max(1, sum(c in r.checks for r in self.results)),
                    4,
                )
                for c in sorted(check_names)
            },
            "judge_mean": round(statistics.fmean(r.verdict.score for r in self.results), 3)
            if self.results
            else 0.0,
            "latency_p95_s": round(latencies[int(0.95 * (len(latencies) - 1))], 4),
            "tokens_total": sum(r.tokens for r in self.results),
            "needs_review": sum(r.needs_review for r in self.results),
        }

    def write(self, out_dir: Path) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "summary.json").write_text(json.dumps(self.summary, indent=2))
        with (out_dir / "results.jsonl").open("w") as fh:
            for r in self.results:
                fh.write(json.dumps(asdict(r), default=str) + "\n")
        with (out_dir / "review_queue.csv").open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(
                [
                    "task_id",
                    "category",
                    "judge_score",
                    "judge_reason",
                    "failures",
                    "answer",
                    "reviewer_score",
                    "reviewer_notes",
                ]
            )
            for r in self.results:
                if r.needs_review:
                    w.writerow(
                        [
                            r.task_id,
                            r.category,
                            r.verdict.score,
                            r.verdict.reason,
                            "; ".join(r.failures),
                            r.answer,
                            "",
                            "",
                        ]
                    )
        (out_dir / "report.md").write_text(self.markdown())

    def markdown(self) -> str:
        s = self.summary
        lines = [
            "# SciAgent evaluation report",
            "",
            f"- Tasks: **{s['tasks']}**, pass rate **{s['pass_rate']:.1%}**",
            f"- Judge mean: {s['judge_mean']} / 5, p95 latency {s['latency_p95_s']} s",
            f"- Routed to human review: {s['needs_review']}",
            "",
            "| Category | Pass rate |",
            "|---|---|",
            *[f"| {c} | {v:.1%} |" for c, v in s["by_category"].items()],
            "",
            "| Check | Rate |",
            "|---|---|",
            *[f"| {c} | {v:.1%} |" for c, v in s["check_rates"].items()],
        ]
        failed = [r for r in self.results if not r.passed]
        if failed:
            lines += ["", "## Failures", ""]
            lines += [f"- `{r.task_id}`: {'; '.join(r.failures)}" for r in failed]
        return "\n".join(lines) + "\n"


def _rate(rs: list[TaskResult]) -> float:
    return round(sum(r.passed for r in rs) / len(rs), 4) if rs else 0.0


class EvalRunner:
    def __init__(
        self,
        agent: SciAgent,
        registry: ToolRegistry,
        judge: Judge | None = None,
        review_threshold: int = 3,
    ) -> None:
        self.agent = agent
        self.registry = registry
        self.judge = judge or HeuristicJudge()
        self.review_threshold = review_threshold

    def run(self, tasks: list[EvalTask]) -> EvalReport:
        return EvalReport([self.run_task(t) for t in tasks])

    def run_task(self, task: EvalTask) -> TaskResult:
        p = task.persona
        principal = Principal(p.user, p.role, frozenset(p.groups))
        res = self.agent.run(task.question, principal, new_id("eval"))
        exp = task.expected
        called = [s["tool"] for s in res.steps if s["decision"] == "allow"]
        denied = [s["tool"] for s in res.steps if s["decision"] == "deny"]
        answer_l = res.answer.lower()

        checks: dict[str, bool] = {"status": res.status == exp.status}
        if exp.tools:
            checks["tool_selection"] = set(exp.tools) <= set(called)
        if exp.denied_tools:
            checks["policy_enforced"] = set(exp.denied_tools) <= set(denied)
        if exp.answer_contains:
            checks["answer_contains"] = all(s.lower() in answer_l for s in exp.answer_contains)
        if exp.answer_excludes:
            checks["answer_excludes"] = not any(s.lower() in answer_l for s in exp.answer_excludes)
        if exp.numbers:
            checks["numeric_grounding"] = all(
                str(dig(self.registry.call(n.tool, n.arguments), n.field)) in res.answer
                for n in exp.numbers
            )
        failures = [name for name, ok in checks.items() if not ok]
        evidence = [s["result"] for s in res.steps if "result" in s]
        verdict = self.judge.grade(task, res.answer, evidence)
        passed = not failures
        return TaskResult(
            task_id=task.id,
            category=task.category,
            passed=passed,
            checks=checks,
            status=res.status,
            answer=res.answer,
            tools_called=called,
            latency_s=res.latency_s,
            tokens=res.prompt_tokens + res.completion_tokens,
            verdict=verdict,
            # Failures, and passes the judge disagrees with, go to human review.
            needs_review=not passed or verdict.score < self.review_threshold,
            failures=failures,
        )
