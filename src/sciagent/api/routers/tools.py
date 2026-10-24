from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from sciagent.api.deps import ContainerDep, PrincipalDep
from sciagent.api.schemas import ToolCallRequest
from sciagent.core.errors import PolicyDenied

router = APIRouter(prefix="/v1/tools", tags=["tools"])


@router.get("")
def list_tools(container: ContainerDep, principal: PrincipalDep) -> list[dict[str, Any]]:
    specs = container.gateway.specs()
    for spec in specs:
        decision = container.policy.evaluate(principal, spec["name"], {})
        spec["allowed"] = decision.allowed
    return specs


@router.post("/{name}:call")
def call_tool(
    name: str, body: ToolCallRequest, container: ContainerDep, principal: PrincipalDep
) -> dict[str, Any]:
    """Invoke a tool directly (outside an agent run), under the same policy."""
    decision = container.policy.evaluate(principal, name, body.arguments)
    container.audit.record(
        actor=principal.user,
        action="tool.call",
        resource=name,
        decision="allow" if decision.allowed else "deny",
        details={"reason": decision.reason, "arguments": body.arguments},
    )
    if not decision.allowed:
        raise PolicyDenied(decision.reason, tool=name)
    return {"tool": name, "result": container.gateway.call(name, body.arguments)}
