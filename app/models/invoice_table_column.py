import uuid

from sqlalchemy import Column, DateTime, Integer, String
from pydantic import BaseModel

from app.database import SupplyBase, msk_now


class InvoiceTableColumn(SupplyBase):
    __tablename__ = "invoice_table_column"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False, index=True)
    column_key = Column(String(50), nullable=False)
    position = Column(Integer, nullable=False)
    is_visible = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    updated_at = Column(DateTime, nullable=True)


class InvoiceTableColumnUpdate(BaseModel):
    column_key: str
    position: int
    is_visible: bool


class InvoiceTableColumnBulkUpdate(BaseModel):
    columns: list[InvoiceTableColumnUpdate]
