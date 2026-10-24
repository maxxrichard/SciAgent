"""The SciAgent LangGraph workflow.

    guard_input ──▶ retrieve ──▶ plan ──▶ (tool calls?) ──▶ authorize ──▶ act ─┐
         │                        ▲            │ no                           │
         ▼                        └────────────┼──────────────────────────────┘
        END                                    ▼
                                         guard_output ──▶ END

Every tool call passes through ``authorize`` (policy engine + audit log) before
``act`` executes it via the configured gateway, so governance cannot be skipped
by the planner.
"""

from __future__ import annotations

import json
import operator
import time
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from sciagent.agent.gateway import ToolGateway
from sciagent.agent.prompts import SYSTEM_PROMPT
from sciagent.core.errors import SciAgentError
from sciagent.core.logging import get_logger
from sciagent.core.security import Principal
from sciagent.core.telemetry import AGENT_RUN_DURATION, LLM_TOKENS
from sciagent.governance.audit import AuditLog
from sciagent.governance.guardrails import check_input, check_output
from sciagent.governance.policy import PolicyEngine
from sciagent.llm.base import LLMClient, ToolCall
from sciagent.retrieval.store import VectorStore

log = get_logger(__name__)

Status = Literal["running", "completed", "blocked", "max_steps", "failed"]


class AgentState(TypedDict, total=False):
    question: str
    principal: Principal
    run_id: str
    messages: Annotated[list[dict[str, Any]], operator.add]
    steps: Annotated[list[dict[str, Any]], operator.add]
    pending: list[ToolCall]
    approved: list[ToolCall]
    call_counts: dict[str, int]
    iterations: int
    prompt_tokens: int
    completion_tokens: int
    answer: str
    status: Status
    violations: list[str]


@dataclass
class AgentResult:
    run_id: str
    status: Status
    answer: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_s: float = 0.0


class SciAgent:
    def __init__(
        self,
        *,
        llm: LLMClient,
        gateway: ToolGateway,
        policy: PolicyEngine,
        audit: AuditLog,
        retriever: VectorStore | None = None,
        max_steps: int = 6,
    ) -> None:
        self.llm = llm
        self.gateway = gateway
        self.policy = policy
        self.audit = audit
        self.retriever = retriever
        self.max_steps = max_steps
        self.graph = self._build()

    # ----------------------------------------------------------------- nodes
    def _guard_input(self, state: AgentState) -> AgentState:
        result = check_input(state["question"])
        if result.allowed:
            return {"violations": []}
        self.audit.record(
            actor=state["principal"].user,
            action="guardrail.input",
            resource=state["run_id"],
            decision="deny",
            details={"violations": result.violations},
        )
        return {
            "status": "blocked",
            "violations": result.violations,
            "answer": "This request was blocked by input guardrails ("
            + ", ".join(result.violations)
            + "). Please rephrase without personal identifiers or instructions to the system.",
        }

    def _retrieve(self, state: AgentState) -> AgentState:
        context = "(none)"
        if self.retriever is not None:
            hits = self.retriever.search(state["question"], k=3)
            if hits:
                context = "\n".join(f"- {d.text}" for d, _ in hits)
        return {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT.format(context=context)},
                {"role": "user", "content": state["question"]},
            ],
            "iterations": 0,
            "call_counts": {},
            "prompt_tokens": 0,
            "completion_tokens": 0,
        }

    def _plan(self, state: AgentState) -> AgentState:
        response = self.llm.chat(state["messages"], self.gateway.specs())
        LLM_TOKENS.labels("prompt").inc(response.usage.prompt_tokens)
        LLM_TOKENS.labels("completion").inc(response.usage.completion_tokens)
        update: AgentState = {
            "iterations": state["iterations"] + 1,
            "prompt_tokens": state["prompt_tokens"] + response.usage.prompt_tokens,
            "completion_tokens": state["completion_tokens"] + response.usage.completion_tokens,
            "pending": response.tool_calls,
        }
        if response.tool_calls:
            update["messages"] = [
                {
                    "role": "assistant",
                    "content": response.content,
                    "tool_calls": [
                        {
                            "id": c.id,
                            "type": "function",
                            "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
                        }
                        for c in response.tool_calls
                    ],
                }
            ]
        else:
            update["answer"] = response.content or ""
        return update

    def _authorize(self, state: AgentState) -> AgentState:
        principal = state["principal"]
        counts = dict(state["call_counts"])
        approved: list[ToolCall] = []
        denied_msgs: list[dict[str, Any]] = []
        steps: list[dict[str, Any]] = []
        for call in state["pending"]:
            decision = self.policy.evaluate(
                principal, call.name, call.arguments, counts.get(call.name, 0)
            )
            self.audit.record(
                actor=principal.user,
                action="tool.authorize",
                resource=call.name,
                decision="allow" if decision.allowed else "deny",
                details={
                    "run_id": state["run_id"],
                    "reason": decision.reason,
                    "arguments": call.arguments,
                },
            )
            if decision.allowed:
                counts[call.name] = counts.get(call.name, 0) + 1
                approved.append(call)
            else:
                steps.append(
                    {
                        "tool": call.name,
                        "arguments": call.arguments,
                        "decision": "deny",
                        "reason": decision.reason,
                    }
                )
                denied_msgs.append(self._tool_msg(call, {"error": f"denied: {decision.reason}"}))
        return {
            "approved": approved,
            "call_counts": counts,
            "messages": denied_msgs,
            "steps": steps,
        }

    def _act(self, state: AgentState) -> AgentState:
        msgs, steps = [], []
        for call in state["approved"]:
            start = time.perf_counter()
            step: dict[str, Any] = {
                "tool": call.name,
                "arguments": call.arguments,
                "decision": "allow",
            }
            try:
                result = self.gateway.call(call.name, call.arguments)
                step["result"] = result
                payload: dict[str, Any] = result
            except SciAgentError as exc:
                step["error"] = exc.message
                payload = {"error": exc.message}
            step["latency_ms"] = round((time.perf_counter() - start) * 1000, 2)
            steps.append(step)
            msgs.append(self._tool_msg(call, payload))
        return {"messages": msgs, "steps": steps, "approved": [], "pending": []}

    def _guard_output(self, state: AgentState) -> AgentState:
        if state.get("status") == "max_steps":
            return {}
        results = [s["result"] for s in state.get("steps", []) if "result" in s]
        checked = check_output(state.get("answer", ""), state["question"], results)
        if checked.violations:
            self.audit.record(
                actor=state["principal"].user,
                action="guardrail.output",
                resource=state["run_id"],
                decision="flag",
                details={"violations": checked.violations},
            )
        return {
            "answer": checked.text,
            "status": "completed",
            "violations": state.get("violations", []) + checked.violations,
        }

    def _max_steps(self, state: AgentState) -> AgentState:
        return {
            "status": "max_steps",
            "answer": f"Stopped after {self.max_steps} planning steps without a final answer.",
        }

    @staticmethod
    def _tool_msg(call: ToolCall, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "role": "tool",
            "tool_call_id": call.id,
            "name": call.name,
            "content": json.dumps(payload, default=str),
        }

    # ----------------------------------------------------------------- edges
    @staticmethod
    def _after_guard(state: AgentState) -> str:
        return "end" if state.get("status") == "blocked" else "retrieve"

    def _after_plan(self, state: AgentState) -> str:
        if not state.get("pending"):
            return "guard_output"
        if state["iterations"] >= self.max_steps:
            return "max_steps"
        return "authorize"

    def _build(self) -> Any:
        g = StateGraph(AgentState)
        g.add_node("guard_input", self._guard_input)
        g.add_node("retrieve", self._retrieve)
        g.add_node("plan", self._plan)
        g.add_node("authorize", self._authorize)
        g.add_node("act", self._act)
        g.add_node("guard_output", self._guard_output)
        g.add_node("max_steps", self._max_steps)
        g.add_edge(START, "guard_input")
        g.add_conditional_edges(
            "guard_input", self._after_guard, {"end": END, "retrieve": "retrieve"}
        )
        g.add_edge("retrieve", "plan")
        g.add_conditional_edges(
            "plan",
            self._after_plan,
            {"authorize": "authorize", "guard_output": "guard_output", "max_steps": "max_steps"},
        )
        g.add_edge("authorize", "act")
        g.add_edge("act", "plan")
        g.add_edge("max_steps", END)
        g.add_edge("guard_output", END)
        return g.compile()

    # ------------------------------------------------------------------- run
    def run(self, question: str, principal: Principal, run_id: str) -> AgentResult:
        start = time.perf_counter()
        status: Status = "failed"
        try:
            final: AgentState = self.graph.invoke(
                {
                    "question": question,
                    "principal": principal,
                    "run_id": run_id,
                    "messages": [],
                    "steps": [],
                },
                {"recursion_limit": 4 * self.max_steps + 10},
            )
            status = final.get("status", "completed")
            return AgentResult(
                run_id=run_id,
                status=status,
                answer=final.get("answer", ""),
                steps=final.get("steps", []),
                violations=final.get("violations", []),
                prompt_tokens=final.get("prompt_tokens", 0),
                completion_tokens=final.get("completion_tokens", 0),
                latency_s=round(time.perf_counter() - start, 4),
            )
        finally:
            AGENT_RUN_DURATION.labels(status).observe(time.perf_counter() - start)
