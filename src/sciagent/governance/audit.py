"""Hash-chained audit log.

Each event stores the SHA-256 of its canonical payload concatenated with the
previous event's hash, so any retroactive edit breaks verification.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select

from sciagent.catalog.db import Database
from sciagent.catalog.models import AuditEvent, utcnow

GENESIS = "0" * 64


def _hash(prev: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256((prev + canonical).encode()).hexdigest()


class AuditLog:
    def __init__(self, db: Database) -> None:
        self.db = db

    def record(
        self,
        *,
        actor: str,
        action: str,
        resource: str,
        decision: str,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        with self.db.session() as s:
            last = s.scalars(select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(1)).first()
            prev = last.hash if last else GENESIS
            ts = utcnow()
            payload = {
                "ts": ts.isoformat(),
                "actor": actor,
                "action": action,
                "resource": resource,
                "decision": decision,
                "details": details or {},
            }
            event = AuditEvent(
                ts=ts,
                actor=actor,
                action=action,
                resource=resource,
                decision=decision,
                details=details or {},
                prev_hash=prev,
                hash=_hash(prev, payload),
            )
            s.add(event)
            s.flush()
            return event

    def events(self, *, actor: str | None = None, limit: int = 100) -> list[AuditEvent]:
        stmt = select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(limit)
        if actor:
            stmt = stmt.where(AuditEvent.actor == actor)
        with self.db.session() as s:
            return list(s.scalars(stmt))

    def verify(self) -> tuple[bool, int | None]:
        """Return ``(ok, first_bad_seq)`` after replaying the whole chain."""
        prev = GENESIS
        with self.db.session() as s:
            for ev in s.scalars(select(AuditEvent).order_by(AuditEvent.seq)):
                ts = ev.ts if ev.ts.tzinfo else ev.ts.replace(tzinfo=utcnow().tzinfo)
                payload = {
                    "ts": ts.isoformat(),
                    "actor": ev.actor,
                    "action": ev.action,
                    "resource": ev.resource,
                    "decision": ev.decision,
                    "details": ev.details,
                }
                if ev.prev_hash != prev or ev.hash != _hash(prev, payload):
                    return False, ev.seq
                prev = ev.hash
        return True, None
