"""Private document exchange between configured sites."""
import hashlib
import os
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import or_, select

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.act import Act, ActFile, ActUserRole
from app.models.contract import Contract, ContractFile, ContractUserRole
from app.models.edo_exchange import EdoDocument, EdoFile, EdoParticipant, EdoRelationship
from app.models.upd_registry import UpdRegistry, UpdRegistryFile, UpdRegistryUserRole
from app.services.edo_store import (decide_document, decide_relationship, event, hub_session,
                                    invite, new_id, participant, tenant_name)

edo_router = APIRouter(prefix="/edo", tags=["EDO"])


class InviteInput(BaseModel):
    participant_id: str = Field(min_length=36, max_length=36)


class DecisionInput(BaseModel):
    decision: Literal["accept", "reject"]
    comment: str | None = Field(default=None, max_length=2000)


class SendInput(BaseModel):
    participant_id: str = Field(min_length=36, max_length=36)
    document_type: Literal["contract", "act", "upd"]
    document_id: int = Field(gt=0)
    file_ids: list[str] = Field(min_length=1, max_length=20)


def authorized(session=Depends(get_session)):
    tenant = tenant_name()
    allowed = {x.strip() for x in os.getenv(f"TENANT_{tenant}_EDO_USERS", "").split(",") if x.strip()}
    if "*" not in allowed and str(session.user_id) not in allowed:
        raise HTTPException(status_code=403, detail="EDO access is not granted")
    return session


def relation_data(row):
    return {k: getattr(row, k) for k in ("id", "participant_low", "participant_high", "invited_by", "status", "created_by", "decided_by", "created_at", "decided_at")}


def document_data(row, files):
    return {**{k: getattr(row, k) for k in ("id", "relationship_id", "sender_id", "recipient_id", "document_type", "source_id", "snapshot", "status", "sent_by", "decided_by", "decision_comment", "sent_at", "decided_at")},
            "files": [{"id": f.id, "name": f.original_name, "size": f.size, "sha256": f.sha256} for f in files]}


def document_for(db, own, document_id):
    doc = db.get(EdoDocument, document_id)
    if not doc or own.id not in (doc.sender_id, doc.recipient_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@edo_router.get("/me")
def me(session=Depends(authorized)):
    with hub_session() as hub:
        own = participant(hub)
        return {"participant_id": own.id}


@edo_router.get("/relationships")
def relationships(session=Depends(authorized)):
    with hub_session() as hub:
        own = participant(hub)
        rows = hub.scalars(select(EdoRelationship).where(or_(EdoRelationship.participant_low == own.id, EdoRelationship.participant_high == own.id)).order_by(EdoRelationship.created_at.desc())).all()
        return [relation_data(r) for r in rows]


@edo_router.post("/relationships", status_code=201)
def invite_site(payload: InviteInput, session=Depends(authorized)):
    with hub_session() as hub:
        return relation_data(invite(hub, participant(hub), payload.participant_id, session.user_id))


@edo_router.post("/relationships/{relationship_id}/decision")
def relationship_decision(relationship_id: str, payload: DecisionInput, session=Depends(authorized)):
    with hub_session() as hub:
        return relation_data(decide_relationship(hub, participant(hub), relationship_id, session.user_id, payload.decision))


@edo_router.post("/documents", status_code=201)
def send_document(payload: SendInput, db: DbSupplySession, session=Depends(authorized)):
    specs = {
        "contract": (Contract, ContractFile, ContractUserRole, "contract_id"),
        "act": (Act, ActFile, ActUserRole, "act_id"),
        "upd": (UpdRegistry, UpdRegistryFile, UpdRegistryUserRole, "upd_id"),
    }
    model, file_model, role_model, parent = specs[payload.document_type]
    source = db.get(model, payload.document_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source document not found")
    assigned = db.scalar(select(role_model.id).where(getattr(role_model, parent) == payload.document_id,
                                                     role_model.user_id == str(session.user_id)).limit(1))
    if str(source.created_by) != str(session.user_id) and assigned is None:
        raise HTTPException(status_code=403, detail="User is not assigned to this document")
    if len(set(payload.file_ids)) != len(payload.file_ids):
        raise HTTPException(status_code=400, detail="Duplicate file IDs")
    files = db.scalars(select(file_model).where(getattr(file_model, parent) == payload.document_id,
                                                file_model.id.in_(payload.file_ids))).all()
    if len(files) != len(payload.file_ids):
        raise HTTPException(status_code=404, detail="Document file not found")
    # An explicit size cap prevents an upload from exhausting process memory or the hub database.
    max_bytes = int(os.getenv("EDO_MAX_DOCUMENT_BYTES", "8388608"))
    content = []
    total = 0
    for f in files:
        try:
            with open(Path(f.file_path), "rb") as handle:
                data = handle.read(max_bytes + 1)
        except OSError:
            raise HTTPException(status_code=409, detail="Document file is unavailable")
        total += len(data)
        if total > max_bytes:
            raise HTTPException(status_code=413, detail="Document files exceed EDO size limit")
        content.append((f, data))
    # Only business fields are sent; paths, internal roles and local database identifiers stay local.
    fields = ("num", "date", "sum", "name", "internal_num", "date_start", "date_end", "comment")
    snapshot = jsonable_encoder({key: getattr(source, key) for key in fields if hasattr(source, key)})
    with hub_session() as hub:
        own = participant(hub)
        low, high = sorted((own.id, payload.participant_id))
        relationship = hub.scalar(select(EdoRelationship).where(EdoRelationship.participant_low == low,
                                  EdoRelationship.participant_high == high).with_for_update())
        if relationship is None or relationship.status != "accepted":
            raise HTTPException(status_code=403, detail="EDO relationship is not accepted")
        doc = EdoDocument(id=new_id(), relationship_id=relationship.id, sender_id=own.id,
                          recipient_id=payload.participant_id, document_type=payload.document_type,
                          source_id=str(payload.document_id), snapshot=snapshot, status="pending", sent_by=str(session.user_id))
        hub.add(doc)
        hub.flush()
        copies = []
        for f, data in content:
            copy = EdoFile(id=new_id(), document_id=doc.id, original_name=(f.original_name or "file")[:255],
                           data=data, size=len(data), sha256=hashlib.sha256(data).hexdigest())
            hub.add(copy)
            copies.append(copy)
        event(hub, "document", doc.id, own.id, session.user_id, "sent")
        hub.flush()
        return document_data(doc, copies)


@edo_router.get("/documents")
def list_documents(direction: Literal["incoming", "outgoing"], session=Depends(authorized)):
    with hub_session() as hub:
        own = participant(hub)
        column = EdoDocument.recipient_id if direction == "incoming" else EdoDocument.sender_id
        docs = hub.scalars(select(EdoDocument).where(column == own.id).order_by(EdoDocument.sent_at.desc()).limit(200)).all()
        return [document_data(doc, []) for doc in docs]


@edo_router.get("/documents/{document_id}")
def get_document(document_id: str, session=Depends(authorized)):
    with hub_session() as hub:
        doc = document_for(hub, participant(hub), document_id)
        files = hub.scalars(select(EdoFile).where(EdoFile.document_id == doc.id).order_by(EdoFile.id)).all()
        return document_data(doc, files)


@edo_router.get("/documents/{document_id}/files/{file_id}")
def download_file(document_id: str, file_id: str, session=Depends(authorized)):
    with hub_session() as hub:
        document_for(hub, participant(hub), document_id)
        file = hub.get(EdoFile, file_id)
        if not file or file.document_id != document_id:
            raise HTTPException(status_code=404, detail="File not found")
        return Response(content=file.data, media_type="application/octet-stream",
                        headers={"Content-Disposition": "attachment; filename*=UTF-8''" + quote(file.original_name, safe="")})


@edo_router.post("/documents/{document_id}/decision")
def document_decision(document_id: str, payload: DecisionInput, session=Depends(authorized)):
    with hub_session() as hub:
        doc = decide_document(hub, participant(hub), document_id, session.user_id, payload.decision, payload.comment)
        files = hub.scalars(select(EdoFile).where(EdoFile.document_id == doc.id)).all()
        return document_data(doc, files)


@edo_router.get("/documents/{document_id}/history")
def document_history(document_id: str, session=Depends(authorized)):
    from app.models.edo_exchange import EdoEvent
    with hub_session() as hub:
        document_for(hub, participant(hub), document_id)
        rows = hub.scalars(select(EdoEvent).where(EdoEvent.object_type == "document", EdoEvent.object_id == document_id).order_by(EdoEvent.created_at, EdoEvent.id)).all()
        return [{key: getattr(row, key) for key in ("id", "participant_id", "user_id", "action", "comment", "created_at")} for row in rows]
