from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import HTTPException, status

from app.models.chat import Attachment, Chat, ChatMember, ChatReadStatus, Message, MessageMention
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.chat_repository import ChatRepository
from app.services.ws_manager import ws_manager

BASE_ATTACHMENTS_DIR = "/home/webserver/models/supply/attachments"


class ChatService:
    def __init__(
        self,
        repo: ChatRepository,
        auth_user_repo: AuthUserRepository | None = None,
        reference_repo=None,
    ) -> None:
        self.repo = repo
        self.auth_user_repo = auth_user_repo
        self.reference_repo = reference_repo

    # ─── Chats ──────────────────────────────────────────────────────────────────

    def get_all(self, user_id: str | None = None):
        chats = self.repo.get_user_chats(user_id) if user_id else self.repo.get_chats()
        return [self._serialize_chat(chat) for chat in chats]

    def _get_member_ids(self, chat_id: int) -> list[str]:
        return [m.user_id for m in self.repo.get_members(chat_id)]

    def get_by_id(self, chat_id: int):
        chat = self.repo.get_chat_by_id(chat_id)
        if not chat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
        return self._serialize_chat(chat)

    def get_by_entity(self, type: str, entity_id: int | str):
        return [self._serialize_chat(chat) for chat in self.repo.get_chats_by_type_and_entity(type, entity_id)]

    def create(self, payload, user_id: str):
        data = payload.model_dump(exclude_unset=True)
        if "created_by" not in data:
            data.pop("created_by", None)
        chat = self.repo.create_chat(data)
        self.repo.add_member(chat.id, user_id)
        return self._serialize_chat(self.repo.get_chat_by_id(chat.id))

    def update(self, chat_id: int, payload):
        chat = self.repo.get_chat_by_id(chat_id)
        if not chat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(chat, key, value)
        updated = self.repo.save_chat(chat)
        return self._serialize_chat(updated)

    def delete(self, chat_id: int):
        chat = self.repo.get_chat_by_id(chat_id)
        if not chat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
        self.repo.delete_chat(chat)
        return None

    # ─── Members ────────────────────────────────────────────────────────────────

    def get_members(self, chat_id: int):
        chat = self.repo.get_chat_by_id(chat_id)
        if not chat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
        return [self._serialize_member(row) for row in self.repo.get_members(chat_id)]

    def add_member(self, chat_id: int, user_id: str):
        chat = self.repo.get_chat_by_id(chat_id)
        if not chat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
        existing = self.repo.get_member(chat_id, user_id)
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a member")
        member = self.repo.add_member(chat_id, user_id)
        return self._serialize_member(member)

    def remove_member(self, chat_id: int, member_id: int):
        members = self.repo.get_members(chat_id)
        member = next((m for m in members if m.id == member_id), None)
        if not member:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
        self.repo.remove_member(member)
        return None

    # ─── Messages ───────────────────────────────────────────────────────────────

    def get_messages(self, chat_id: int, user_id: str | None = None):
        chat = self.repo.get_chat_by_id(chat_id)
        if not chat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
        messages = self.repo.get_messages(chat_id)
        if user_id:
            self._mark_read(chat_id, user_id, messages[0].id if messages else 0)
        return [self._serialize_message(msg) for msg in messages]

    def create_message(self, chat_id: int, payload, sender_id: str):
        chat = self.repo.get_chat_by_id(chat_id)
        if not chat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
        data = {"sender_id": sender_id, "message_text": payload.message_text}
        message = self.repo.create_message(chat_id, data)

        mention_ids = payload.mentions or []
        if "all" in mention_ids:
            members = self.repo.get_members(chat_id)
            mention_ids = [m.user_id for m in members]

        chat.updated_at = None
        self.repo.save_chat(chat)

        serialized = self._serialize_message(message)

        member_ids = self._get_member_ids(chat_id)
        ws_manager.send_new_message(member_ids, chat_id, serialized, sender_id)

        for mention_user_id in mention_ids:
            if mention_user_id != sender_id:
                self.repo.create_mention(message.id, mention_user_id)
                unviewed = self.repo.get_unviewed_mentions_count(chat_id, mention_user_id)
                ws_manager.send_mention(member_ids, chat_id, message.id, mention_user_id, unviewed)
                self._push_badge_for_user(mention_user_id)

        return serialized

    def update_message(self, chat_id: int, message_id: int, payload):
        message = self.repo.get_message_by_id(message_id)
        if not message or message.chat_id != chat_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(message, key, value)
        updated = self.repo.save_message(message)
        serialized = self._serialize_message(updated)
        member_ids = self._get_member_ids(chat_id)
        ws_manager.send_message_updated(member_ids, chat_id, serialized)
        return serialized

    def delete_message(self, chat_id: int, message_id: int):
        message = self.repo.get_message_by_id(message_id)
        if not message or message.chat_id != chat_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
        self.repo.delete_message(message)
        member_ids = self._get_member_ids(chat_id)
        ws_manager.send_message_deleted(member_ids, chat_id, message_id)
        return None

    # ─── Attachments ────────────────────────────────────────────────────────────

    def upload_attachment(self, message_id: int, file_name: str, file_bytes: bytes, file_type: str):
        message = self.repo.get_message_by_id(message_id)
        if not message:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
        extension = Path(file_name).suffix.lower().lstrip(".")
        storage_name = f"{uuid.uuid4().hex}{('.' + extension) if extension else ''}"
        target_dir = os.path.join(BASE_ATTACHMENTS_DIR, str(message.chat_id), str(message_id))
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, storage_name)
        with open(file_path, "wb") as f:
            f.write(file_bytes)
        attachment = self.repo.create_attachment(
            message_id,
            {"file_name": file_name, "storage_name": storage_name, "file_path": file_path, "file_type": file_type},
        )
        return self._serialize_attachment(attachment)

    def get_attachments(self, message_id: int):
        return [self._serialize_attachment(row) for row in self.repo.get_attachments(message_id)]

    def delete_attachment(self, attachment_id: int):
        attachment = self.repo.get_attachment_by_id(attachment_id)
        if not attachment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
        if attachment.file_path and os.path.exists(attachment.file_path):
            os.remove(attachment.file_path)
        self.repo.delete_attachment(attachment)
        return None

    def download_attachment(self, attachment_id: int) -> tuple[str, str]:
        attachment = self.repo.get_attachment_by_id(attachment_id)
        if not attachment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
        if not attachment.file_path or not os.path.exists(attachment.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")
        return attachment.file_path, attachment.file_name

    # ─── Read Status ────────────────────────────────────────────────────────────

    def get_read_status(self, chat_id: int, user_id: str):
        row = self.repo.get_read_status(chat_id, user_id)
        last_chat_message = self.repo.get_last_message_id(chat_id)
        if row:
            return {
                "id": row.id,
                "chat_id": row.chat_id,
                "user_id": row.user_id,
                "last_read_message_id": row.last_read_message_id,
                "last_chat_message": last_chat_message,
                "updated_at": row.updated_at,
            }
        return {
            "chat_id": chat_id,
            "user_id": user_id,
            "last_read_message_id": None,
            "last_chat_message": last_chat_message,
            "updated_at": None,
        }

    def mark_read(self, chat_id: int, user_id: str, last_read_message_id: int):
        self.repo.upsert_read_status(chat_id, user_id, last_read_message_id)
        member_ids = self._get_member_ids(chat_id)
        ws_manager.send_read_status(member_ids, chat_id, user_id, last_read_message_id)
        return {"status": "ok"}

    def _mark_read(self, chat_id: int, user_id: str, last_message_id: int) -> None:
        if last_message_id:
            self.repo.upsert_read_status(chat_id, user_id, last_message_id)

    # ─── Mentions ───────────────────────────────────────────────────────────────

    def get_mentions(self, user_id: str, chat_id: int | None = None):
        if chat_id is not None:
            mentions = self.repo.get_mentions_by_chat_and_user(chat_id, user_id)
        else:
            mentions = self.repo.get_mentions_by_user(user_id)
        return [self._serialize_mention(m) for m in mentions]

    def batch_update_mentions(self, chat_id: int, user_id: str, payload):
        mentions = self.repo.get_mentions_by_chat_and_user(chat_id, user_id)
        if not mentions:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No mentions found")
        mention_ids = [m.id for m in mentions]
        data = payload.model_dump(exclude_unset=True) if payload else {}
        if data:
            self.repo.bulk_update_mentions(mention_ids, data)
        result = [self._serialize_mention(m) for m in self.repo.get_mentions_by_chat_and_user(chat_id, user_id)]
        self._push_badge_for_user(user_id)
        return result

    def get_mention(self, mention_id: int):
        mention = self.repo.get_mention_by_id(mention_id)
        if not mention:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mention not found")
        return self._serialize_mention(mention)

    def update_mention(self, mention_id: int, payload):
        mention = self.repo.get_mention_by_id(mention_id)
        if not mention:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mention not found")
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(mention, key, value)
        updated = self.repo.save_mention(mention)
        from app.services.ws_manager import ws_manager
        self._push_badge_for_user(updated.user_id)
        return self._serialize_mention(updated)

    # ─── My chats ──────────────────────────────────────────────────────────

    def get_my_chats(self, user_id: str):
        chats = self.repo.get_user_chats(user_id)
        result = []
        for chat in chats:
            last_message = self.repo.get_last_message_id(chat.id)
            read_status = self.repo.get_read_status(chat.id, user_id)
            last_read_id = read_status.last_read_message_id if read_status else 0
            unread = (last_message or 0) - last_read_id if last_message and last_read_id else 0
            if unread < 0:
                unread = 0
            has_unviewed_mention = self.repo.get_unviewed_mentions_count(chat.id, user_id) > 0
            title, project_name, project_type, project_id = self._build_chat_meta(chat, user_id)
            result.append({
                "id": chat.id,
                "type": chat.type,
                "user_id": chat.user_id,
                "invoice_id": chat.invoice_id,
                "request_id": chat.request_id,
                "delivery_id": chat.delivery_id,
                "specification_id": chat.specification_id,
                "deal_id": chat.deal_id,
                "created_at": chat.created_at,
                "updated_at": chat.updated_at,
                "title": title,
                "project_name": project_name,
                "project_type": project_type,
                "project_id": project_id,
                "has_unviewed_mention": has_unviewed_mention,
                "unread_count": unread,
                "last_message_id": last_message,
                "last_read_message_id": last_read_id if last_read_id else None,
            })
        return result

    def _build_chat_meta(self, chat: Chat, viewer_user_id: str | None = None):
        title = None
        project_name = None
        project_type = None
        project_id = None

        if chat.type == "personal":
            target_user_id = chat.user_id if chat.user_id != viewer_user_id else None
            if not target_user_id and viewer_user_id:
                members = self.repo.get_members(chat.id)
                for m in members:
                    if m.user_id != viewer_user_id:
                        target_user_id = m.user_id
                        break
            if target_user_id and self.auth_user_repo:
                users = self.auth_user_repo.get_by_ids([target_user_id])
                if users:
                    u = users[0]
                    title = f"{u.name or ''} {u.surname or ''} {u.patronymic or ''}".strip()

        elif chat.type == "invoice" and chat.invoice_id:
            row = self.repo.get_invoice_num(chat.invoice_id)
            if row:
                title = f"Чат по счету № {row}"
            ol_row = self.repo.get_invoice_object_levels_id(chat.invoice_id)
            if ol_row:
                object_levels_id, obj_type = ol_row
                if obj_type == "object" and object_levels_id:
                    project_type = "object"
                    project_id = object_levels_id
                    if self.reference_repo:
                        objects = self.reference_repo.get_objects_by_ids([object_levels_id])
                        if objects:
                            project_name = objects[0].short_name or objects[0].full_name
                elif object_levels_id:
                    project_type = "object_levels_id"
                    project_id = object_levels_id
                    project_name = self._build_project_name_from_level(object_levels_id)

        elif chat.type == "request" and chat.request_id:
            row = self.repo.get_request_name(chat.request_id)
            if row:
                name, object_levels_id = row
                title = f"Чат по заявке {name}" if name else None
                if object_levels_id:
                    project_type = "object_levels_id"
                    project_id = object_levels_id
                    project_name = self._build_project_name_from_level(object_levels_id)

        elif chat.type == "specification" and chat.specification_id:
            row = self.repo.get_specification_name(chat.specification_id)
            if row:
                name, object_levels_id = row
                title = f"Чат по спецификации {name}" if name else None
                if object_levels_id:
                    project_type = "object_levels_id"
                    project_id = object_levels_id
                    project_name = self._build_project_name_from_level(object_levels_id)

        elif chat.type == "deal" and chat.deal_id:
            row = self.repo.get_deal_name(chat.deal_id)
            if row:
                name, object_id = row
                title = f"Чат по сделке {name}" if name else None
                if object_id:
                    project_type = "object"
                    project_id = object_id
                    if self.reference_repo:
                        objects = self.reference_repo.get_objects_by_ids([object_id])
                        if objects:
                            project_name = objects[0].short_name or objects[0].full_name

        elif chat.type == "delivery":
            title = "Чат по доставке"

        return title, project_name, project_type, project_id

    def _build_project_name_from_level(self, object_levels_id: str) -> str | None:
        if not self.reference_repo or not object_levels_id:
            return None
        from app.services.project_name_builder import build_project_name, load_project_reference_maps
        levels_by_id, objects_by_id, contracts_by_id, work_types_by_id = load_project_reference_maps(
            self.reference_repo, [object_levels_id]
        )
        return build_project_name(
            object_levels_id, levels_by_id, objects_by_id, contracts_by_id, work_types_by_id
        )




    # ─── Serialization ──────────────────────────────────────────────────────────

    def _serialize_chat(self, chat: Chat) -> dict:
        members = [self._serialize_member(m) for m in self.repo.get_members(chat.id)]
        messages = self.repo.get_messages(chat.id)
        last_message = self._serialize_message(messages[0]) if messages else None
        return {
            "id": chat.id,
            "type": chat.type,
            "user_id": chat.user_id,
            "invoice_id": chat.invoice_id,
            "request_id": chat.request_id,
            "delivery_id": chat.delivery_id,
            "specification_id": chat.specification_id,
            "deal_id": chat.deal_id,
            "created_at": chat.created_at,
            "updated_at": chat.updated_at,
            "last_message": last_message,
            "members": members,
        }

    def _serialize_member(self, member: ChatMember) -> dict:
        user = self._get_user(member.user_id) if self.auth_user_repo else None
        return {
            "id": member.id,
            "chat_id": member.chat_id,
            "user_id": member.user_id,
            "user": user,
        }

    def _serialize_message(self, msg: Message) -> dict:
        sender = self._get_user(msg.sender_id) if self.auth_user_repo else None
        attachments = [self._serialize_attachment(a) for a in self.repo.get_attachments(msg.id)]
        mentions = [self._serialize_mention(m) for m in self.repo.get_mentions_by_message(msg.id)]
        return {
            "id": msg.id,
            "chat_id": msg.chat_id,
            "sender_id": msg.sender_id,
            "sender": sender,
            "message_text": msg.message_text,
            "created_at": msg.created_at,
            "attachments": attachments,
            "mentions": mentions,
        }

    @staticmethod
    def _serialize_attachment(att: Attachment) -> dict:
        return {
            "id": att.id,
            "message_id": att.message_id,
            "file_name": att.file_name,
            "storage_name": att.storage_name,
            "file_path": att.file_path,
            "file_type": att.file_type,
            "created_at": att.created_at,
        }

    def _serialize_mention(self, mention: MessageMention) -> dict:
        user = self._get_user(mention.user_id) if self.auth_user_repo else None
        return {
            "id": mention.id,
            "message_id": mention.message_id,
            "user_id": mention.user_id,
            "user": user,
            "chat_id": mention.chat_id,
            "is_notified": mention.is_notified,
            "is_viewed": mention.is_viewed,
            "created_at": mention.created_at,
        }

    def _get_user(self, user_id: str) -> dict | None:
        if not self.auth_user_repo:
            return None
        users = self.auth_user_repo.get_by_ids([user_id])
        if not users:
            return None
        user = users[0]
        return {
            "id": user.id,
            "name": user.name,
            "surname": user.surname,
            "patronymic": user.patronymic,
        }

    def _push_badge_for_user(self, user_id: str) -> None:
        from app.database import SupplySessionLocal
        from app.repositories.invoice_repository import InvoiceRepository
        from app.services.ws_manager import ws_manager
        try:
            db = SupplySessionLocal()
            try:
                repo = InvoiceRepository(db)
                counts = repo.get_badge_counts(user_id)
                ws_manager.send_badge_counts(user_id, counts)
            finally:
                db.close()
        except Exception:
            pass
