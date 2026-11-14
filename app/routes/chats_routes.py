from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from app.database import DbAuthSession, DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.chat import (
    AddMemberRequest,
    ChatCreate,
    ChatUpdate,
    MessageCreate,
    MessageUpdate,
    ReadStatusUpdate,
)
from app.models.session import SessionDB
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.chat_repository import ChatRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.services.chat_service import ChatService

chats_router = APIRouter(prefix="/chats", tags=["Chats"])


def build_service(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession | None = None,
) -> ChatService:
    return ChatService(
        ChatRepository(supply_db),
        AuthUserRepository(auth_db),
        ReferenceObjectRepository(reference_db) if reference_db else None,
    )


# ─── Chats ──────────────────────────────────────────────────────────────────────

@chats_router.get("/unread-count", status_code=status.HTTP_200_OK)
def get_unread_count(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    session: SessionDB = Depends(get_session),
):
    return build_service(supply_db, auth_db).get_unread_count(str(session.user_id))


@chats_router.get("/my", status_code=status.HTTP_200_OK)
def get_my_chats(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
    user_id: str | None = Query(default=None),
):
    target_user = user_id or str(session.user_id)
    return build_service(supply_db, auth_db, reference_db).get_my_chats(target_user)


@chats_router.get("", status_code=status.HTTP_200_OK)
def get_chats(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    session: SessionDB = Depends(get_session),
    type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
):
    service = build_service(supply_db, auth_db)
    if type and entity_id:
        if type in ("invoice", "request"):
            entity_id_int = int(entity_id)
        else:
            entity_id_int = entity_id
        return service.get_by_entity(type, entity_id_int)
    return service.get_all(str(session.user_id))


@chats_router.get("/{chat_id}", status_code=status.HTTP_200_OK)
def get_chat(
    chat_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).get_by_id(chat_id)


@chats_router.post("", status_code=status.HTTP_201_CREATED)
def create_chat(
    payload: ChatCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    session: SessionDB = Depends(get_session),
):
    return build_service(supply_db, auth_db).create(payload, str(session.user_id))


@chats_router.patch("/read-all", status_code=status.HTTP_200_OK)
def mark_all_chats_read(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    session: SessionDB = Depends(get_session),
):
    return build_service(supply_db, auth_db).mark_all_chats_read(str(session.user_id))


@chats_router.patch("/{chat_id}", status_code=status.HTTP_200_OK)
def update_chat(
    chat_id: int,
    payload: ChatUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).update(chat_id, payload)


@chats_router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat(
    chat_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    build_service(supply_db, auth_db).delete(chat_id)
    return None


# ─── Members ────────────────────────────────────────────────────────────────────

@chats_router.get("/{chat_id}/members", status_code=status.HTTP_200_OK)
def get_members(
    chat_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).get_members(chat_id)


@chats_router.post("/{chat_id}/members", status_code=status.HTTP_201_CREATED)
def add_member(
    chat_id: int,
    payload: AddMemberRequest,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).add_member(chat_id, payload.user_id)


@chats_router.delete("/{chat_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    chat_id: int,
    member_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    build_service(supply_db, auth_db).remove_member(chat_id, member_id)
    return None


@chats_router.delete("/{chat_id}/members/by-user/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member_by_user_id(
    chat_id: int,
    user_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    build_service(supply_db, auth_db).remove_member_by_user_id(chat_id, user_id)
    return None


# ─── Messages ───────────────────────────────────────────────────────────────────

@chats_router.get("/{chat_id}/messages", status_code=status.HTTP_200_OK)
def get_messages(
    chat_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    session: SessionDB = Depends(get_session),
):
    return build_service(supply_db, auth_db).get_messages(chat_id, str(session.user_id))


@chats_router.post("/{chat_id}/messages", status_code=status.HTTP_201_CREATED)
def create_message(
    chat_id: int,
    payload: MessageCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    session: SessionDB = Depends(get_session),
):
    return build_service(supply_db, auth_db).create_message(chat_id, payload, str(session.user_id))


@chats_router.patch("/{chat_id}/messages/{message_id}", status_code=status.HTTP_200_OK)
def update_message(
    chat_id: int,
    message_id: int,
    payload: MessageUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).update_message(chat_id, message_id, payload)


@chats_router.delete("/{chat_id}/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_message(
    chat_id: int,
    message_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    build_service(supply_db, auth_db).delete_message(chat_id, message_id)
    return None


# ─── Attachments ────────────────────────────────────────────────────────────────


def _check_attachment_access(service, chat_id, message_id, user_id, attachment_id=None):
    if not service.repo.get_member(chat_id, str(user_id)):
        raise HTTPException(status_code=403, detail="Not a chat member")
    message = service.repo.get_message_by_id(message_id)
    if not message or message.chat_id != chat_id:
        raise HTTPException(status_code=404, detail="Message not found")
    if attachment_id is not None:
        attachment = service.repo.get_attachment_by_id(attachment_id)
        if not attachment or attachment.message_id != message_id:
            raise HTTPException(status_code=404, detail="Attachment not found")
    return message


@chats_router.post("/{chat_id}/messages/{message_id}/attachments", status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    chat_id: int,
    message_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
    file: UploadFile = File(...),
):
    service = build_service(supply_db, auth_db)
    message = _check_attachment_access(service, chat_id, message_id, _session.user_id)
    if str(message.sender_id) != str(_session.user_id):
        raise HTTPException(status_code=403, detail="Only the sender can attach files")
    file_bytes = await file.read()
    return await run_in_threadpool(
        service.upload_attachment,
        message_id,
        file.filename or "file",
        file_bytes,
        file.content_type or "application/octet-stream",
    )


@chats_router.get("/{chat_id}/messages/{message_id}/attachments", status_code=status.HTTP_200_OK)
def get_attachments(
    chat_id: int,
    message_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    service = build_service(supply_db, auth_db)
    _check_attachment_access(service, chat_id, message_id, _session.user_id)
    return service.get_attachments(message_id)


@chats_router.get("/{chat_id}/messages/{message_id}/attachments/{attachment_id}/content")
def attachment_content(chat_id: int, message_id: int, attachment_id: int,
                       supply_db: DbSupplySession, auth_db: DbAuthSession,
                       session: SessionDB = Depends(get_session)):
    service = build_service(supply_db, auth_db)
    message = service.repo.get_message_by_id(message_id)
    attachment = service.repo.get_attachment_by_id(attachment_id)
    if not service.repo.get_member(chat_id, str(session.user_id)):
        raise HTTPException(status_code=403, detail="Not a chat member")
    if not message or message.chat_id != chat_id or not attachment or attachment.message_id != message_id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    file_path, filename = service.download_attachment(attachment_id)
    # Only known raster formats are displayed inline; active content is downloaded.
    from pathlib import Path
    allowed = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp"}
    mime = allowed.get(Path(filename).suffix.lower())
    return FileResponse(file_path, media_type=mime or "application/octet-stream", filename=filename,
                        content_disposition_type="inline" if mime else "attachment",
                        headers={"X-Content-Type-Options": "nosniff"})


@chats_router.get("/{chat_id}/messages/{message_id}/attachments/{attachment_id}/download", status_code=status.HTTP_200_OK)
def download_attachment(
    chat_id: int,
    message_id: int,
    attachment_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    service = build_service(supply_db, auth_db)
    _check_attachment_access(service, chat_id, message_id, _session.user_id, attachment_id)
    file_path, filename = service.download_attachment(attachment_id)
    return FileResponse(file_path, filename=filename)


@chats_router.get("/{chat_id}/messages/{message_id}/attachments/{attachment_id}/preview", status_code=status.HTTP_200_OK)
def preview_attachment(
    chat_id: int,
    message_id: int,
    attachment_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    service = build_service(supply_db, auth_db)
    _check_attachment_access(service, chat_id, message_id, _session.user_id, attachment_id)
    file_path = service.preview_attachment(attachment_id)
    return FileResponse(file_path, media_type="application/pdf")


@chats_router.delete("/{chat_id}/messages/{message_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(
    chat_id: int,
    message_id: int,
    attachment_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    service = build_service(supply_db, auth_db)
    message = _check_attachment_access(service, chat_id, message_id, _session.user_id, attachment_id)
    if str(message.sender_id) != str(_session.user_id):
        raise HTTPException(status_code=403, detail="Only the sender can delete attachments")
    service.delete_attachment(attachment_id)
    return None


# ─── Read Status ────────────────────────────────────────────────────────────────

@chats_router.get("/{chat_id}/read-status", status_code=status.HTTP_200_OK)
def get_read_status(
    chat_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    session: SessionDB = Depends(get_session),
    user_id: str | None = Query(default=None),
):
    target_user = user_id or str(session.user_id)
    return build_service(supply_db, auth_db).get_read_status(chat_id, target_user)


@chats_router.patch("/{chat_id}/read-status", status_code=status.HTTP_200_OK)
def mark_read(
    chat_id: int,
    payload: ReadStatusUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    session: SessionDB = Depends(get_session),
):
    return build_service(supply_db, auth_db).mark_read(chat_id, str(session.user_id), payload.last_read_message_id)
