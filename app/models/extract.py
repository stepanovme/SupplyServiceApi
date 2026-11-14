import uuid
from datetime import date as dt_date
from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, text

from app.database import SupplyBase


class Extract(SupplyBase):
    __tablename__ = "extracts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_number = Column(String(100), nullable=True)
    counterparties_id = Column(CHAR(36), nullable=True, index=True)
    date = Column(Date, nullable=True)
    date_start = Column(Date, nullable=True)
    date_end = Column(Date, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    created_by = Column(CHAR(36), nullable=False, index=True)


class ExtractItem(SupplyBase):
    __tablename__ = "extract_item"

    id = Column(CHAR(36), primary_key=True)
    extract_id = Column(Integer, ForeignKey("extracts.id", ondelete="CASCADE"), nullable=False, index=True)
    debet_counterparties_id = Column(CHAR(36), nullable=True, index=True)
    credit_counterparties_id = Column(CHAR(36), nullable=True, index=True)
    date = Column(Date, nullable=True)
    debit = Column(Float(17, 8), nullable=True)
    credit = Column(Float(17, 8), nullable=True)
    num_document = Column(Integer, nullable=True)
    bank_name = Column(Text, nullable=True)
    payment_purpose = Column(Text, nullable=True)


class ExtractFile(SupplyBase):
    __tablename__ = "extract_file"

    id = Column(CHAR(36), primary_key=True)
    extract_id = Column(Integer, ForeignKey("extracts.id", ondelete="CASCADE"), nullable=False, index=True)
    original_name = Column(Text, nullable=False)
    storage_name = Column(Text, nullable=False)
    extension = Column(String(100), nullable=True)
    mime_type = Column(String(300), nullable=True)
    file_path = Column(Text, nullable=False)
    uploaded_by = Column(CHAR(36), nullable=False)
    uploaded_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class ExtractItemPayment(SupplyBase):
    __tablename__ = "extract_item_payments"

    id = Column(CHAR(36), primary_key=True)
    extract_item_id = Column(CHAR(36), ForeignKey("extract_item.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id = Column(CHAR(36), nullable=False)
    type = Column(String(100), nullable=False)
    created_at = Column(DateTime, nullable=False)
    created_by = Column(CHAR(36), nullable=False, index=True)


class ExtractCreate(BaseModel):
    account_number: str | None = Field(default=None)
    counterparties_id: str | None = Field(default=None)
    date: dt_date | None = Field(default=None)
    date_start: dt_date | None = Field(default=None)
    date_end: dt_date | None = Field(default=None)


class ExtractUpdate(BaseModel):
    account_number: str | None = Field(default=None)
    counterparties_id: str | None = Field(default=None)
    date: dt_date | None = Field(default=None)
    date_start: dt_date | None = Field(default=None)
    date_end: dt_date | None = Field(default=None)


class ExtractItemCreate(BaseModel):
    id: str | None = Field(default=None)
    debet_counterparties_id: str | None = Field(default=None)
    credit_counterparties_id: str | None = Field(default=None)
    date: dt_date | None = Field(default=None)
    debit: float | None = Field(default=None)
    credit: float | None = Field(default=None)
    num_document: int | None = Field(default=None)
    bank_name: str | None = Field(default=None)
    payment_purpose: str | None = Field(default=None)


class ExtractItemUpdate(BaseModel):
    debet_counterparties_id: str | None = Field(default=None)
    credit_counterparties_id: str | None = Field(default=None)
    date: dt_date | None = Field(default=None)
    debit: float | None = Field(default=None)
    credit: float | None = Field(default=None)
    num_document: int | None = Field(default=None)
    bank_name: str | None = Field(default=None)
    payment_purpose: str | None = Field(default=None)


class ExtractItemPaymentCreate(BaseModel):
    extract_item_id: str
    source_id: str
    type: str
    created_at: datetime | None = Field(default=None)


class ExtractItemPaymentUpdate(BaseModel):
    source_id: str | None = Field(default=None)
    type: str | None = Field(default=None)
