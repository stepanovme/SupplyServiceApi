from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Column, DateTime, Integer, String, Text, Boolean

from app.database import SupplyBase, msk_now


class NotificationFeed(SupplyBase):
    __tablename__ = "notification_feed"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(CHAR(36), nullable=False, index=True)
    type = Column(String(50), nullable=False)
    title = Column(String(500), nullable=True)
    body = Column(Text, nullable=True)
    object_type = Column(String(50), nullable=True)
    object_id = Column(String(36), nullable=True)
    related_user_id = Column(CHAR(36), nullable=True)
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)


class NotificationFeedCreate(BaseModel):
    user_id: str = Field()
    type: str = Field()
    title: str | None = Field(default=None)
    body: str | None = Field(default=None)
    object_type: str | None = Field(default=None)
    object_id: str | None = Field(default=None)
    related_user_id: str | None = Field(default=None)


class NotificationFeedUpdate(BaseModel):
    is_read: bool | None = Field(default=None)
