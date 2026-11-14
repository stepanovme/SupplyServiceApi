from sqlalchemy import Boolean, Column, DateTime, Integer, String, text
from app.database import SupplyBase


class IOSPushDevice(SupplyBase):
    __tablename__ = "ios_push_devices"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False, index=True)
    token = Column(String(200), nullable=False, unique=True)
    environment = Column(String(16), nullable=False)
    active = Column(Boolean, nullable=False, server_default=text("1"))
    updated_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))
