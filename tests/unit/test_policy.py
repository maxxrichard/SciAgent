from pathlib import Path

from sciagent.core.security import Principal
from sciagent.governance.policy import PolicyEngine, ToolRule


def test_policy_file_covers_every_registered_tool(policy, registry):
    assert set(policy.rules) == set(registry.names())


def test_allows_member_of_group(policy, alice):
    d = policy.evaluate(alice, "segment_cells", {"sample_id": "IMG-0001"})
    assert d.allowed and d.reason == "allowed"


def test_denies_unknown_tool(policy, alice):
    d = policy.evaluate(alice, "rm_rf", {})
    assert not d.allowed and "not registered" in d.reason


def test_denies_non_member(policy, bob):
    d = policy.evaluate(bob, "annotate_variants", {"sample_id": "WGS-0001"})
    assert not d.allowed and "genomics" in d.reason


def test_enforces_budget_and_row_limits(policy, alice):
    assert not policy.evaluate(alice, "survival_analysis", {}, calls_so_far=2).allowed
    assert not policy.evaluate(alice, "annotate_variants", {"limit": 10_000}).allowed
    assert policy.evaluate(alice, "annotate_variants", {"limit": 100}).allowed


def test_role_and_classification_rules(alice, admin):
    engine = PolicyEngine(
        rules={
            "secret": ToolRule(
                "secret", "clinical", frozenset({"researcher", "admin"}), "restricted"
            ),
            "admin_only": ToolRule("admin_only", "clinical", frozenset({"admin"})),
        }
    )
    assert not engine.evaluate(alice, "secret", {}).allowed
    assert engine.evaluate(admin, "secret", {}).allowed
    assert "role" in engine.evaluate(alice, "admin_only", {}).reason


def test_loads_custom_file(tmp_path: Path):
    f = tmp_path / "p.yaml"
    f.write_text("tools:\n  t:\n    group: g\n    roles: [analyst]\n")
    engine = PolicyEngine.from_file(f)
    assert engine.rules["t"].roles == frozenset({"analyst"})
    assert engine.evaluate(Principal("a", "analyst", frozenset({"g"})), "t", {}).allowed
