"""EDO hub connection and transactional state transitions."""
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import _engines, current_tenant
from app.models.edo_exchange import EdoDocument, EdoEvent, EdoParticipant, EdoRelationship


def new_id():
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@contextmanager
def hub_session():
    hub = os.getenv("EDO_HUB_TENANT")
    if not hub or hub not in _engines:
        raise HTTPException(status_code=503, detail="EDO hub is not configured")
    with Session(_engines[hub]["supply"], expire_on_commit=False) as db:
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise


def tenant_name():
    tenant = current_tenant.get()
    if tenant is None:
        raise HTTPException(status_code=503, detail="Site is not configured")
    return tenant


def participant(db):
    row = db.scalar(select(EdoParticipant).where(EdoParticipant.tenant == tenant_name()))
    if row is None:
        raise HTTPException(status_code=503, detail="EDO participant is not registered")
    return row


def event(db, kind, object_id, actor, user_id, action, comment=None):
    db.add(EdoEvent(id=new_id(), object_type=kind, object_id=object_id, participant_id=actor,
                    user_id=str(user_id), action=action, comment=comment))


def invite(db, own, target_id, user_id):
    if target_id == own.id:
        raise HTTPException(status_code=400, detail="Cannot invite your own site")
    target = db.get(EdoParticipant, target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="EDO participant not found")
    low, high = sorted((own.id, target_id))
    row = db.scalar(select(EdoRelationship).where(EdoRelationship.participant_low == low,
                    EdoRelationship.participant_high == high).with_for_update())
    if row is not None:
        if row.status != "rejected":
            raise HTTPException(status_code=409, detail="Relationship already exists")
        row.invited_by, row.status, row.created_by = own.id, "pending", str(user_id)
        row.decided_by, row.decided_at, row.created_at = None, None, now()
    else:
        row = EdoRelationship(id=new_id(), participant_low=low, participant_high=high,
                              invited_by=own.id, status="pending", created_by=str(user_id))
        db.add(row)
    event(db, "relationship", row.id, own.id, user_id, "invited")
    try:
        db.flush()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Relationship already exists")
    return row


def decide_relationship(db, own, relationship_id, user_id, decision):
    row = db.scalar(select(EdoRelationship).where(EdoRelationship.id == relationship_id).with_for_update())
    if not row or own.id not in (row.participant_low, row.participant_high):
        raise HTTPException(status_code=404, detail="Relationship not found")
    if row.invited_by == own.id or row.status != "pending":
        raise HTTPException(status_code=409, detail="Relationship cannot be decided")
    row.status = "accepted" if decision == "accept" else "rejected"
    row.decided_by, row.decided_at = str(user_id), now()
    event(db, "relationship", row.id, own.id, user_id, row.status)
    db.flush()
    return row


def decide_document(db, own, document_id, user_id, decision, comment):
    row = db.scalar(select(EdoDocument).where(EdoDocument.id == document_id).with_for_update())
    if not row or row.recipient_id != own.id:
        raise HTTPException(status_code=404, detail="Incoming document not found")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail="Document already decided")
    row.status = "accepted" if decision == "accept" else "rejected"
    row.decided_by, row.decided_at, row.decision_comment = str(user_id), now(), comment
    event(db, "document", row.id, own.id, user_id, row.status, comment)
    db.flush()
    return row
