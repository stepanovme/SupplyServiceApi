from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.database import SupplyBase, msk_now


class PushSubscription(SupplyBase):
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False, index=True)
    endpoint = Column(Text, nullable=False)
    p256dh = Column(Text, nullable=False)
    auth = Column(Text, nullable=False)
    device_type = Column(String(20), nullable=False, default="desktop")
    user_agent = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    updated_at = Column(DateTime, nullable=False, default=msk_now, onupdate=msk_now)
