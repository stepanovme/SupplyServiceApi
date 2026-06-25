from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.chat import Attachment, Chat, ChatMember, ChatReadStatus, Message, MessageMention


class ChatRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ─── Chat ───────────────────────────────────────────────────────────────────

    def get_chats(self) -> list[Chat]:
        return self.db.query(Chat).order_by(Chat.updated_at.desc(), Chat.created_at.desc(), Chat.id.desc()).all()

    def get_chat_by_id(self, chat_id: int) -> Chat | None:
        return self.db.query(Chat).filter(Chat.id == chat_id).first()

    def get_chats_by_type_and_entity(self, type: str, entity_id: int | str) -> list[Chat]:
        col = {
            "invoice": Chat.invoice_id,
            "request": Chat.request_id,
            "delivery": Chat.delivery_id,
            "specification": Chat.specification_id,
            "deal": Chat.deal_id,
        }.get(type)
        if col is None:
            return []
        return self.db.query(Chat).filter(Chat.type == type, col == entity_id).all()

    def get_user_chats(self, user_id: str) -> list[Chat]:
        return (
            self.db.query(Chat)
            .join(ChatMember, ChatMember.chat_id == Chat.id)
            .filter(ChatMember.user_id == user_id)
            .order_by(Chat.updated_at.desc(), Chat.created_at.desc(), Chat.id.desc())
            .all()
        )

    def create_chat(self, payload: dict) -> Chat:
        row = Chat(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_chat(self, row: Chat) -> Chat:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_chat(self, row: Chat) -> None:
        self.db.delete(row)
        self.db.commit()

    # ─── Chat Members ───────────────────────────────────────────────────────────

    def get_members(self, chat_id: int) -> list[ChatMember]:
        return self.db.query(ChatMember).filter(ChatMember.chat_id == chat_id).all()

    def get_member(self, chat_id: int, user_id: str) -> ChatMember | None:
        return (
            self.db.query(ChatMember)
            .filter(ChatMember.chat_id == chat_id, ChatMember.user_id == user_id)
            .first()
        )

    def add_member(self, chat_id: int, user_id: str) -> ChatMember:
        row = ChatMember(chat_id=chat_id, user_id=user_id)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def remove_member(self, row: ChatMember) -> None:
        self.db.delete(row)
        self.db.commit()

    # ─── Messages ───────────────────────────────────────────────────────────────

    def get_messages(self, chat_id: int) -> list[Message]:
        return (
            self.db.query(Message)
            .filter(Message.chat_id == chat_id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .all()
        )

    def get_message_by_id(self, message_id: int) -> Message | None:
        return self.db.query(Message).filter(Message.id == message_id).first()

    def get_last_message_id(self, chat_id: int) -> int | None:
        message = (
            self.db.query(Message)
            .filter(Message.chat_id == chat_id)
            .order_by(Message.id.desc())
            .first()
        )
        return message.id if message else None

    def create_message(self, chat_id: int, payload: dict) -> Message:
        row = Message(chat_id=chat_id, **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_message(self, row: Message) -> Message:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_message(self, row: Message) -> None:
        self.db.delete(row)
        self.db.commit()

    # ─── Attachments ────────────────────────────────────────────────────────────

    def get_attachments(self, message_id: int) -> list[Attachment]:
        return self.db.query(Attachment).filter(Attachment.message_id == message_id).order_by(Attachment.created_at.asc()).all()

    def get_attachment_by_id(self, attachment_id: int) -> Attachment | None:
        return self.db.query(Attachment).filter(Attachment.id == attachment_id).first()

    def create_attachment(self, message_id: int, payload: dict) -> Attachment:
        row = Attachment(message_id=message_id, **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_attachment(self, row: Attachment) -> None:
        self.db.delete(row)
        self.db.commit()

    # ─── Read Status ────────────────────────────────────────────────────────────

    def get_read_status(self, chat_id: int, user_id: str) -> ChatReadStatus | None:
        return (
            self.db.query(ChatReadStatus)
            .filter(ChatReadStatus.chat_id == chat_id, ChatReadStatus.user_id == user_id)
            .first()
        )

    def upsert_read_status(self, chat_id: int, user_id: str, last_read_message_id: int) -> ChatReadStatus:
        row = self.get_read_status(chat_id, user_id)
        if row:
            row.last_read_message_id = last_read_message_id
        else:
            row = ChatReadStatus(chat_id=chat_id, user_id=user_id, last_read_message_id=last_read_message_id)
            self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    # ─── Mentions ───────────────────────────────────────────────────────────────

    def get_mentions_by_user(self, user_id: str) -> list[MessageMention]:
        return (
            self.db.query(MessageMention)
            .filter(MessageMention.user_id == user_id)
            .order_by(MessageMention.created_at.desc())
            .all()
        )

    def create_mention(self, message_id: int, user_id: str) -> MessageMention:
        from app.models.chat import Message
        message = self.db.query(Message).filter(Message.id == message_id).first()
        chat_id = message.chat_id if message else 0
        row = MessageMention(message_id=message_id, chat_id=chat_id, user_id=user_id)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_mention(self, row: MessageMention) -> MessageMention:
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_mention_by_id(self, mention_id: int) -> MessageMention | None:
        return self.db.query(MessageMention).filter(MessageMention.id == mention_id).first()

    def get_mentions_by_message(self, message_id: int) -> list[MessageMention]:
        return self.db.query(MessageMention).filter(MessageMention.message_id == message_id).all()

    def get_mentions_by_chat_and_user(self, chat_id: int, user_id: str) -> list[MessageMention]:
        return (
            self.db.query(MessageMention)
            .filter(MessageMention.chat_id == chat_id, MessageMention.user_id == user_id)
            .order_by(MessageMention.created_at.desc())
            .all()
        )

    def bulk_update_mentions(self, mention_ids: list[int], data: dict) -> None:
        if not mention_ids:
            return
        self.db.query(MessageMention).filter(MessageMention.id.in_(mention_ids)).update(data, synchronize_session=False)
        self.db.commit()

    # ─── Entity helpers ─────────────────────────────────────────────────────

    def get_invoice_num(self, invoice_id: int) -> str | None:
        from app.models.invoice import Invoice
        row = self.db.query(Invoice.num).filter(Invoice.id == invoice_id).first()
        return row[0] if row else None

    def get_invoice_object_levels_id(self, invoice_id: int) -> str | None:
        from app.models.invoice import Invoice
        row = self.db.query(Invoice.object_levels_id, Invoice.object_type).filter(Invoice.id == invoice_id).first()
        return row

    def get_request_name(self, request_id: int) -> str | None:
        from app.models.supply_request import SupplyRequest
        row = self.db.query(SupplyRequest.name, SupplyRequest.object_levels_id).filter(SupplyRequest.id == request_id).first()
        return row

    def get_specification_name(self, specification_id: str) -> str | None:
        from app.models.specification import Specification
        row = self.db.query(Specification.name, Specification.object_levels_id).filter(Specification.id == specification_id).first()
        return row

    def get_deal_name(self, deal_id: str) -> str | None:
        from app.models.deal import Deal
        row = self.db.query(Deal.name, Deal.object_id).filter(Deal.id == deal_id).first()
        return row

    def get_unviewed_mentions_count(self, chat_id: int, user_id: str) -> int:
        return (
            self.db.query(MessageMention)
            .filter(MessageMention.chat_id == chat_id, MessageMention.user_id == user_id, MessageMention.is_viewed == False)
            .count()
        )
