from tests.conftest import ADMIN_KEY, IMAGING_ONLY_KEY, RESEARCHER_KEY, auth


def test_health_ready_and_metrics(client):
    assert client.get("/healthz").json()["status"] == "ok"
    ready = client.get("/readyz")
    assert ready.status_code == 200 and ready.json()["checks"]["database"]
    client.get("/healthz")
    body = client.get("/metrics").text
    assert 'sciagent_http_requests_total{method="GET",route="/healthz",service="api"' in body


def test_readyz_reports_unhealthy_database(client, container, monkeypatch):
    monkeypatch.setattr(container.db, "ping", lambda: False)
    assert client.get("/readyz").status_code == 503


def test_requires_api_key(client):
    r = client.get("/v1/tools")
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthenticated"
    assert r.headers["x-request-id"]


def test_query_end_to_end_and_run_history(client):
    r = client.post(
        "/v1/query",
        headers=auth(RESEARCHER_KEY),
        json={"question": "Were there any heart rate anomalies for PT-00012?"},
    )
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["status"] == "completed" and run["steps"][0]["tool"] == "detect_vital_anomalies"
    assert run["user"] == "alice" and run["model"] == "rule-based-planner"

    assert client.get(f"/v1/runs/{run['id']}", headers=auth(RESEARCHER_KEY)).status_code == 200
    assert client.get(f"/v1/runs/{run['id']}", headers=auth(IMAGING_ONLY_KEY)).status_code == 404
    assert client.get(f"/v1/runs/{run['id']}", headers=auth(ADMIN_KEY)).status_code == 200
    mine = client.get("/v1/runs", headers=auth(RESEARCHER_KEY)).json()
    assert [x["id"] for x in mine] == [run["id"]]
    assert client.get("/v1/runs", headers=auth(IMAGING_ONLY_KEY)).json() == []


def test_query_validation_and_failure(client, container, monkeypatch):
    assert (
        client.post("/v1/query", headers=auth(RESEARCHER_KEY), json={"question": "x"}).status_code
        == 422
    )
    from sciagent.core.errors import ToolExecutionError

    def boom(*a, **k):
        raise ToolExecutionError("gateway down")

    monkeypatch.setattr(container.agent, "run", boom)
    r = client.post("/v1/query", headers=auth(RESEARCHER_KEY), json={"question": "cells IMG-0001"})
    assert r.status_code == 502
    runs = client.get("/v1/runs", headers=auth(RESEARCHER_KEY)).json()
    assert runs[0]["status"] == "failed"


def test_tools_listing_marks_allowed(client):
    tools = {t["name"]: t for t in client.get("/v1/tools", headers=auth(IMAGING_ONLY_KEY)).json()}
    assert tools["segment_cells"]["allowed"] and not tools["annotate_variants"]["allowed"]


def test_direct_tool_call_is_governed(client):
    ok = client.post(
        "/v1/tools/segment_cells:call",
        headers=auth(IMAGING_ONLY_KEY),
        json={"arguments": {"sample_id": "IMG-0001"}},
    )
    assert ok.status_code == 200 and ok.json()["result"]["cell_count"] > 0
    denied = client.post(
        "/v1/tools/build_cohort:call", headers=auth(IMAGING_ONLY_KEY), json={"arguments": {}}
    )
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "policy_denied"
    invalid = client.post(
        "/v1/tools/segment_cells:call",
        headers=auth(IMAGING_ONLY_KEY),
        json={"arguments": {"sample_id": "x"}},
    )
    assert invalid.status_code == 422 and invalid.json()["error"]["details"]["errors"]


DATASET = {
    "name": "icu-vitals",
    "modality": "clinical",
    "group": "clinical",
    "uri": "s3://lake/curated/clinical/icu-vitals/v=1",
    "row_count": 10,
    "schema": {"hour": "int64"},
    "description": "ICU vitals",
}


def test_dataset_registration_requires_admin_and_respects_groups(client):
    assert (
        client.post("/v1/datasets", headers=auth(RESEARCHER_KEY), json=DATASET).status_code == 403
    )
    created = client.post("/v1/datasets", headers=auth(ADMIN_KEY), json=DATASET)
    assert created.status_code == 201, created.text
    ds = created.json()
    assert ds["version"] == 1 and ds["schema"] == {"hour": "int64"}
    again = client.post("/v1/datasets", headers=auth(ADMIN_KEY), json=DATASET).json()
    assert again["version"] == 2

    listed = client.get("/v1/datasets?modality=clinical", headers=auth(RESEARCHER_KEY)).json()
    assert {d["version"] for d in listed} == {1, 2}
    assert client.get("/v1/datasets", headers=auth(IMAGING_ONLY_KEY)).json() == []
    assert client.get(f"/v1/datasets/{ds['id']}", headers=auth(RESEARCHER_KEY)).status_code == 200
    assert client.get(f"/v1/datasets/{ds['id']}", headers=auth(IMAGING_ONLY_KEY)).status_code == 403
    assert client.get("/v1/datasets/ds_missing", headers=auth(ADMIN_KEY)).status_code == 404

    hits = client.get("/v1/search?q=icu vitals", headers=auth(RESEARCHER_KEY)).json()
    assert any(h["id"].startswith("dataset:") for h in hits)


def test_audit_endpoints_are_admin_only(client):
    client.post(
        "/v1/tools/segment_cells:call",
        headers=auth(RESEARCHER_KEY),
        json={"arguments": {"sample_id": "IMG-0001"}},
    )
    assert client.get("/v1/audit/events", headers=auth(RESEARCHER_KEY)).status_code == 403
    events = client.get("/v1/audit/events?actor=alice", headers=auth(ADMIN_KEY)).json()
    assert events[0]["action"] == "tool.call"
    assert client.get("/v1/audit/verify", headers=auth(ADMIN_KEY)).json() == {
        "intact": True,
        "first_bad_seq": None,
    }


def test_lifespan_builds_container_when_not_injected(settings):
    from fastapi.testclient import TestClient

    from sciagent.api.main import create_app

    with TestClient(create_app(settings)) as c:
        assert c.get("/readyz").status_code == 200
