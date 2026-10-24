import json
from pathlib import Path

import pytest

from sciagent.eval.gate import evaluate_gate, load_gate
from sciagent.eval.harness import build_runner
from sciagent.eval.judge import HeuristicJudge, LLMJudge
from sciagent.eval.runner import dig
from sciagent.eval.tasks import EvalTask, load_tasks
from sciagent.llm.base import LLMResponse

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def report():
    return build_runner().run(load_tasks(ROOT / "evals/tasks"))


def test_curated_suite_covers_every_category():
    tasks = load_tasks(ROOT / "evals/tasks")
    assert {t.category for t in tasks} == {
        "imaging",
        "genomics",
        "clinical",
        "harmonisation",
        "governance",
        "safety",
    }
    assert len(tasks) >= 50


def test_reference_agent_passes_release_gate(report):
    problems = evaluate_gate(report.summary, load_gate(ROOT / "evals/gate.yaml"))
    assert problems == [], report.markdown()


def test_report_artifacts(report, tmp_path):
    report.write(tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["tasks"] == len(report.results)
    assert (tmp_path / "results.jsonl").read_text().count("\n") == len(report.results)
    assert (tmp_path / "review_queue.csv").read_text().startswith("task_id")
    assert "# SciAgent evaluation report" in (tmp_path / "report.md").read_text()


def test_failures_are_reported_and_routed_to_review(tmp_path):
    task = EvalTask.model_validate(
        {
            "id": "t",
            "category": "imaging",
            "question": "How many nuclei are in IMG-0001?",
            "expected": {
                "tools": ["expression_qc"],
                "answer_contains": ["zebra"],
                "answer_excludes": ["nuclei"],
                "denied_tools": ["segment_cells"],
            },
        }
    )
    rep = build_runner().run([task])
    r = rep.results[0]
    assert not r.passed and r.needs_review
    assert set(r.failures) == {
        "tool_selection",
        "answer_contains",
        "answer_excludes",
        "policy_enforced",
    }
    assert "## Failures" in rep.markdown()
    rep.write(tmp_path)
    assert "t,imaging" in (tmp_path / "review_queue.csv").read_text()


def test_gate_reports_each_violation():
    summary = {
        "pass_rate": 0.5,
        "by_category": {"safety": 0.9},
        "check_rates": {},
        "judge_mean": 2.0,
        "latency_p95_s": 9.0,
    }
    thresholds = {
        "min_pass_rate": 0.9,
        "min_category_pass_rate": {"safety": 1.0, "imaging": 0.9},
        "min_check_rate": {"tool_selection": 0.9},
        "min_judge_mean": 3,
        "max_latency_p95_s": 5,
    }
    assert len(evaluate_gate(summary, thresholds)) == 6


def test_load_tasks_rejects_bad_input(tmp_path):
    f = tmp_path / "t.jsonl"
    f.write_text('{"id": "a", "category": "imaging", "question": "q"}\n// comment\n\n')
    assert len(load_tasks(f)) == 1
    f.write_text('{"id": "a", "category": "nope", "question": "q"}\n')
    with pytest.raises(ValueError, match=r"t\.jsonl:1"):
        load_tasks(f)
    f.write_text('{"id": "a", "category": "imaging", "question": "q"}\n' * 2)
    with pytest.raises(ValueError, match="duplicate"):
        load_tasks(f)


def test_dig():
    assert dig({"a": [{"b": 3}]}, "a.0.b") == 3


def test_heuristic_judge():
    task = EvalTask(id="x", category="imaging", question="q", rubric="Reports nuclei count")
    j = HeuristicJudge()
    assert j.grade(task, "", []).score == 1
    assert j.grade(task, "12 nuclei counted", []).score == 5
    assert j.grade(task, "12 nuclei counted. could not be traced", []).score == 3


class FakeLLM:
    model = "fake"

    def __init__(self, content):
        self.content = content

    def chat(self, messages, tools):
        return LLMResponse(self.content)


def test_llm_judge_parses_and_clamps():
    task = EvalTask(id="x", category="imaging", question="q")
    assert LLMJudge(FakeLLM('Sure: {"score": 4, "reason": "good"}')).grade(task, "a", []).score == 4
    assert LLMJudge(FakeLLM('{"score": 9}')).grade(task, "a", []).score == 5
    assert LLMJudge(FakeLLM("no json")).grade(task, "a", []).reason == "unparseable judge output"
    assert build_runner(judge_llm=FakeLLM('{"score": 2}')).judge.name == "llm"
