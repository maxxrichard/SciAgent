"""Assemble an isolated agent for evaluation (in-memory DB, local tools)."""

from __future__ import annotations

from sciagent.agent import LocalToolGateway, SciAgent
from sciagent.catalog.db import Database
from sciagent.eval.judge import HeuristicJudge, Judge, LLMJudge
from sciagent.eval.runner import EvalRunner
from sciagent.governance.audit import AuditLog
from sciagent.governance.policy import PolicyEngine
from sciagent.llm.base import LLMClient
from sciagent.llm.rule_based import RuleBasedLLM
from sciagent.tools import default_registry


def build_runner(llm: LLMClient | None = None, judge_llm: LLMClient | None = None) -> EvalRunner:
    db = Database("sqlite+pysqlite:///:memory:")
    db.create_all()
    registry = default_registry()
    agent = SciAgent(
        llm=llm or RuleBasedLLM(),
        gateway=LocalToolGateway(registry),
        policy=PolicyEngine.from_file(),
        audit=AuditLog(db),
    )
    judge: Judge = LLMJudge(judge_llm) if judge_llm else HeuristicJudge()
    return EvalRunner(agent, registry, judge)
