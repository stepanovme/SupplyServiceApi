from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import CHAR, Column, DateTime, Text

from app.database import SupplyBase


class InvoicePaymentFile(SupplyBase):
    __tablename__ = "invoice_payment_file"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_payment_id = Column(CHAR(36), nullable=False, index=True)
    original_name = Column(Text, nullable=False)
    storage_name = Column(Text, nullable=False)
    file_path = Column(Text, nullable=False)
    uploaded_by = Column(CHAR(36), nullable=False, index=True)
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class InvoicePaymentFileCreate(BaseModel):
    original_name: str
    storage_name: str
    file_path: str


class InvoicePaymentFileUpdate(BaseModel):
    original_name: str | None = None


class InvoicePaymentFileResponse(BaseModel):
    id: str
    invoice_payment_id: str
    original_name: str
    storage_name: str
    file_path: str
    uploaded_by: str
    uploaded_at: datetime
