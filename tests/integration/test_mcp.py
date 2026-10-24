import asyncio

import pytest
from mcp.client import Client

from sciagent.agent import McpToolGateway, SciAgent
from sciagent.core.errors import NotFoundError, ToolExecutionError
from sciagent.llm.rule_based import RuleBasedLLM
from sciagent.mcp_servers import SERVER_NAMES, build_server

pytestmark = pytest.mark.integration


def test_servers_partition_the_registry(registry):
    async def names(server):
        async with Client(build_server(server, registry)) as c:
            return {t.name for t in (await c.list_tools()).tools}

    seen = [asyncio.run(names(s)) for s in SERVER_NAMES]
    assert set().union(*seen) == set(registry.names())
    assert sum(len(s) for s in seen) == 8


def test_mcp_schema_keeps_constraints(registry):
    async def schema():
        async with Client(build_server("imaging", registry)) as c:
            tools = {t.name: t for t in (await c.list_tools()).tools}
            return tools["segment_cells"].input_schema

    props = asyncio.run(schema())["properties"]
    assert props["sample_id"]["pattern"] == r"^IMG-\d{4}$"


def test_unknown_server():
    with pytest.raises(ValueError):
        build_server("proteomics")


def test_gateway_calls_over_mcp(registry):
    gw = McpToolGateway(registry, {n: build_server(n, registry) for n in SERVER_NAMES})
    assert len(gw.specs()) == 8
    out = gw.call("build_cohort", {"diagnosis": "copd", "limit": 2})
    assert out == registry.call("build_cohort", {"diagnosis": "copd", "limit": 2})
    with pytest.raises(ToolExecutionError, match="validation"):
        gw.call("segment_cells", {"sample_id": "bad"})
    partial = McpToolGateway(registry, {"imaging": build_server("imaging", registry)})
    assert {s["server"] for s in partial.specs()} == {"imaging"}
    with pytest.raises(NotFoundError):
        partial.call("build_cohort", {})


def test_agent_runs_through_mcp(registry, policy, audit, alice):
    gw = McpToolGateway(registry, {n: build_server(n, registry) for n in SERVER_NAMES})
    agent = SciAgent(llm=RuleBasedLLM(), gateway=gw, policy=policy, audit=audit)
    res = agent.run("Run single-cell QC on SC-0001", alice, "r")
    assert res.status == "completed" and res.steps[0]["result"]["cells"] == 400


def test_mcp_server_exposes_metrics_and_health(registry):
    from starlette.testclient import TestClient

    app = build_server("clinical", registry).streamable_http_app()
    with TestClient(app) as c:
        assert c.get("/healthz").json() == {"status": "ok", "server": "clinical"}
        assert "sciagent_tool_calls_total" in c.get("/metrics").text
