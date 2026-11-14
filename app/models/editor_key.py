import uuid

from sqlalchemy import Column, DateTime, Integer, String

from app.database import SupplyBase, msk_now


class EditorKey(SupplyBase):
    __tablename__ = "editor_key"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(Integer, nullable=False, index=True)
    key = Column(String(200), nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
