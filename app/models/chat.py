from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy import JSON, CHAR, Column, DateTime, Enum, ForeignKey, Integer, Text, Boolean

from app.database import SupplyBase


class Chat(SupplyBase):
    __tablename__ = "chat"

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(Enum("personal", "invoice", "request", "delivery", "specification", "deal"), nullable=False)
    user_id = Column(CHAR(36), nullable=True, index=True)
    invoice_id = Column(Integer, nullable=True, index=True)
    request_id = Column(Integer, nullable=True, index=True)
    delivery_id = Column(CHAR(36), nullable=True, index=True)
    specification_id = Column(CHAR(36), nullable=True, index=True)
    deal_id = Column(CHAR(36), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)


class ChatMember(SupplyBase):
    __tablename__ = "chat_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(Integer, ForeignKey("chat.id"), nullable=False, index=True)
    user_id = Column(CHAR(36), nullable=False, index=True)


class Message(SupplyBase):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(Integer, ForeignKey("chat.id"), nullable=False, index=True)
    sender_id = Column(CHAR(36), nullable=False, index=True)
    message_text = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Attachment(SupplyBase):
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False, index=True)
    file_name = Column(Text, nullable=False)
    storage_name = Column(Text, nullable=False)
    file_path = Column(Text, nullable=False)
    file_type = Column(CHAR(100), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ChatReadStatus(SupplyBase):
    __tablename__ = "chat_read_status"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(Integer, ForeignKey("chat.id"), nullable=False, index=True)
    user_id = Column(CHAR(36), nullable=False, index=True)
    last_read_message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class MessageMention(SupplyBase):
    __tablename__ = "message_mentions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False, index=True)
    chat_id = Column(Integer, ForeignKey("chat.id"), nullable=False, index=True)
    user_id = Column(CHAR(36), nullable=False, index=True)
    is_notified = Column(Boolean, nullable=False, default=False)
    is_viewed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


# ─── Pydantic schemas ───────────────────────────────────────────────────────────

class ChatCreate(BaseModel):
    type: str
    user_id: str | None = Field(default=None)
    invoice_id: int | None = Field(default=None)
    request_id: int | None = Field(default=None)
    delivery_id: str | None = Field(default=None)
    specification_id: str | None = Field(default=None)
    deal_id: str | None = Field(default=None)


class ChatUpdate(BaseModel):
    type: str | None = Field(default=None)
    user_id: str | None = Field(default=None)
    invoice_id: int | None = Field(default=None)
    request_id: int | None = Field(default=None)
    delivery_id: str | None = Field(default=None)
    specification_id: str | None = Field(default=None)
    deal_id: str | None = Field(default=None)


class ChatResponse(BaseModel):
    id: int
    type: str
    user_id: str | None = None
    invoice_id: int | None = None
    request_id: int | None = None
    delivery_id: str | None = None
    specification_id: str | None = None
    deal_id: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    last_message: dict | None = None
    unread_count: int = 0
    members: list[dict] = Field(default_factory=list)


class MessageCreate(BaseModel):
    message_text: str | None = Field(default=None)
    mentions: list[str] | None = Field(
        default=None,
        description="UUID пользователей из authorization_service.users. Передавать ['all'], чтобы упомянуть всех участников чата",
        examples=[["6e8f6b50-1312-11f1-aa8c-bc241127d0bd"], ["all"]],
    )


class MessageUpdate(BaseModel):
    message_text: str | None = None


class MessageResponse(BaseModel):
    id: int
    chat_id: int
    sender_id: str
    sender: dict | None = None
    message_text: str | None = None
    created_at: datetime
    attachments: list[dict] = Field(default_factory=list)
    mentions: list[dict] = Field(default_factory=list)


class AttachmentResponse(BaseModel):
    id: int
    message_id: int
    file_name: str
    storage_name: str
    file_path: str
    file_type: str
    created_at: datetime


class ChatMemberResponse(BaseModel):
    id: int
    chat_id: int
    user_id: str
    user: dict | None = None


class ChatReadStatusResponse(BaseModel):
    chat_id: int
    user_id: str
    last_read_message_id: int
    updated_at: datetime


class ReadStatusUpdate(BaseModel):
    last_read_message_id: int


class MentionUpdate(BaseModel):
    is_viewed: bool | None = None
    is_notified: bool | None = None


class AddMemberRequest(BaseModel):
    user_id: str
