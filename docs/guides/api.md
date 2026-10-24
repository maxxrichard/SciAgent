# API usage

All endpoints except `/healthz`, `/readyz` and `/metrics` require an `x-api-key` header.
OpenAPI docs are served at `/docs`.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/query` | Run the agent on a question; returns the persisted run with steps |
| `GET` | `/v1/runs`, `/v1/runs/{id}` | Run history (own runs; admins see all) |
| `GET` | `/v1/tools` | Tool specs with an `allowed` flag for the caller |
| `POST` | `/v1/tools/{name}:call` | Direct, policy-checked tool invocation |
| `GET` | `/v1/datasets`, `/v1/datasets/{id}` | Catalog, filtered to the caller's groups |
| `POST` | `/v1/datasets` | Register a dataset version (admin) |
| `GET` | `/v1/search?q=` | Semantic search over tools and datasets |
| `GET` | `/v1/audit/events`, `/v1/audit/verify` | Audit trail and chain verification (admin) |

Errors share one shape:

```json
{"error": {"code": "policy_denied", "message": "user not in data group 'genomics'",
           "details": {"tool": "annotate_variants"}}, "request_id": "4b1f..."}
```

```python
import httpx

client = httpx.Client(base_url="http://localhost:8000", headers={"x-api-key": "dev-researcher-key"})
run = client.post("/v1/query", json={"question": "Run single-cell QC on SC-0003"}).json()
print(run["answer"])
for step in run["steps"]:
    print(step["tool"], step["decision"], step.get("latency_ms"))
```
