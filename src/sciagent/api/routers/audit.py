from __future__ import annotations

from fastapi import APIRouter, Query

from sciagent.api.deps import AdminDep, ContainerDep
from sciagent.api.schemas import AuditEventOut
from sciagent.catalog.models import AuditEvent

router = APIRouter(prefix="/v1/audit", tags=["audit"])


@router.get("/events", response_model=list[AuditEventOut])
def events(
    container: ContainerDep,
    _: AdminDep,
    actor: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
) -> list[AuditEvent]:
    return container.audit.events(actor=actor, limit=limit)


@router.get("/verify")
def verify(container: ContainerDep, _: AdminDep) -> dict[str, object]:
    ok, bad = container.audit.verify()
    return {"intact": ok, "first_bad_seq": bad}
