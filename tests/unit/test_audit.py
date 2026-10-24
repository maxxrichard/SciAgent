from sqlalchemy import update

from sciagent.catalog.models import AuditEvent
from sciagent.governance.audit import GENESIS


def test_chain_links_and_verifies(audit):
    e1 = audit.record(actor="a", action="x", resource="r1", decision="allow")
    e2 = audit.record(actor="b", action="y", resource="r2", decision="deny", details={"k": 1})
    assert e1.prev_hash == GENESIS and e2.prev_hash == e1.hash
    assert audit.verify() == (True, None)
    assert [e.actor for e in audit.events()] == ["b", "a"]
    assert [e.actor for e in audit.events(actor="a")] == ["a"]


def test_detects_tampering(audit, db):
    audit.record(actor="a", action="x", resource="r1", decision="deny")
    audit.record(actor="a", action="x", resource="r2", decision="deny")
    with db.session() as s:
        s.execute(update(AuditEvent).where(AuditEvent.seq == 1).values(decision="allow"))
    assert audit.verify() == (False, 1)


def test_empty_chain_is_valid(audit):
    assert audit.verify() == (True, None)
