from datetime import datetime, timedelta

from sqlalchemy import CHAR, Boolean, Column, DateTime, Integer, String

from app.database import SupplyBase


def msk_now():
    return datetime.utcnow() + timedelta(hours=3)


class VkUserLink(SupplyBase):
    __tablename__ = "vk_user_links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(CHAR(36), nullable=False, index=True)
    vk_id = Column(String(100), nullable=False)
    notifications_enabled = Column(Boolean, nullable=False, default=True)
    ref = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
