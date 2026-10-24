"""Attribute-based policy for tool access.

Policies are declared in ``policies.yaml`` and evaluated before every tool call.
A decision is a pure function of (principal, tool, arguments, run budget), which
keeps it easy to test and to explain in the audit log.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from sciagent.core.security import Principal

DEFAULT_POLICY_FILE = Path(__file__).with_name("policies.yaml")


@dataclass(frozen=True)
class ToolRule:
    tool: str
    group: str
    roles: frozenset[str]
    classification: str = "internal"
    max_calls_per_run: int = 5
    max_rows: int | None = None


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    rule: str | None = None


@dataclass
class PolicyEngine:
    rules: dict[str, ToolRule] = field(default_factory=dict)
    restricted_classifications: frozenset[str] = frozenset({"restricted"})

    @classmethod
    def from_file(cls, path: Path = DEFAULT_POLICY_FILE) -> PolicyEngine:
        raw = yaml.safe_load(path.read_text())
        rules = {
            name: ToolRule(
                tool=name,
                group=spec["group"],
                roles=frozenset(spec.get("roles", ["researcher", "analyst", "admin"])),
                classification=spec.get("classification", "internal"),
                max_calls_per_run=int(spec.get("max_calls_per_run", 5)),
                max_rows=spec.get("max_rows"),
            )
            for name, spec in raw["tools"].items()
        }
        return cls(rules=rules)

    def evaluate(
        self,
        principal: Principal,
        tool: str,
        arguments: dict[str, Any],
        calls_so_far: int = 0,
    ) -> Decision:
        rule = self.rules.get(tool)
        if rule is None:
            return Decision(False, f"tool '{tool}' is not registered in policy")
        if principal.role not in rule.roles:
            return Decision(False, f"role '{principal.role}' may not call '{tool}'", tool)
        if not principal.in_group(rule.group):
            return Decision(False, f"user not in data group '{rule.group}'", tool)
        if rule.classification in self.restricted_classifications and not principal.is_admin:
            return Decision(False, "restricted data requires admin approval", tool)
        if calls_so_far >= rule.max_calls_per_run:
            return Decision(
                False, f"per-run budget of {rule.max_calls_per_run} calls exceeded", tool
            )
        limit = arguments.get("limit")
        if rule.max_rows is not None and isinstance(limit, int) and limit > rule.max_rows:
            return Decision(False, f"limit {limit} exceeds max_rows {rule.max_rows}", tool)
        return Decision(True, "allowed", tool)
