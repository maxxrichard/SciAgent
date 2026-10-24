from __future__ import annotations

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from sciagent import __version__
from sciagent.api.deps import ContainerDep
from sciagent.core.telemetry import REGISTRY

router = APIRouter(tags=["ops"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/readyz")
def readyz(container: ContainerDep) -> JSONResponse:
    checks = {"database": container.db.ping(), "tools": bool(container.registry.names())}
    ok = all(checks.values())
    return JSONResponse({"ready": ok, "checks": checks}, status_code=200 if ok else 503)


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
