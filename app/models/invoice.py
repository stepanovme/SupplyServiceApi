from datetime import date as dt_date
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text

from app.database import SupplyBase


class Invoice(SupplyBase):
    __tablename__ = "invoice"

    id = Column(Integer, primary_key=True, autoincrement=True)
    object_levels_id = Column(CHAR(36), nullable=True, index=True)
    num = Column(String(100), nullable=True)
    date = Column(Date, nullable=True)
    request_id = Column(Integer, nullable=True, index=True)
    file_id = Column(CHAR(36), nullable=True, index=True)
    provider_id = Column(CHAR(36), nullable=True, index=True)
    payer_id = Column(CHAR(36), nullable=True, index=True)
    is_delivery_included = Column(Boolean, nullable=False, default=False)
    prepayment_percent = Column(Float, nullable=False, default=0)
    due_days = Column(Integer, nullable=False, default=0)
    valid_until = Column(Integer, nullable=False, default=0)
    is_urgent = Column(Boolean, nullable=False, default=False)
    total_amount = Column(Float, nullable=False, default=0)
    vat_rate = Column(Integer, nullable=False, default=0)
    vat_amount = Column(Float, nullable=False, default=0)
    status = Column(CHAR(36), ForeignKey("status.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True)
    created_by = Column(CHAR(36), nullable=False)


class InvoiceItem(SupplyBase):
    __tablename__ = "invoice_items"

    id = Column(CHAR(36), primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoice.id"), nullable=False, index=True)
    name = Column(Text, nullable=True)
    unit_name = Column(String(30), nullable=True)
    quantity = Column(Float, nullable=True)
    price = Column(Float, nullable=True)
    sum = Column(Float, nullable=True)
    nds = Column(Integer, nullable=True)
    value_nds = Column(Integer, nullable=True)
    unit_id = Column(CHAR(36), nullable=True)
    converted_quantity = Column(Float, nullable=True)


class InvoiceLog(SupplyBase):
    __tablename__ = "invoice_log"

    id = Column(CHAR(36), primary_key=True)
    user_id = Column(CHAR(36), nullable=False, index=True)
    invoice_id = Column(Integer, ForeignKey("invoice.id"), nullable=False, index=True)
    type = Column(String(20), nullable=True)
    status_name = Column(String(20), nullable=True)
    date_response = Column(DateTime, nullable=True)


class InvoicePayment(SupplyBase):
    __tablename__ = "invoice_payment"

    id = Column(CHAR(36), primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoice.id"), nullable=False, index=True)
    value = Column(Float, nullable=True)
    date_plan = Column(Date, nullable=True)
    created_by = Column(CHAR(36), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True)
    paid = Column(Float, nullable=True)
    paid_type = Column(String(30), nullable=True)
    paid_by = Column(CHAR(36), nullable=True, index=True)
    paid_at = Column(DateTime, nullable=True)
    file_id = Column(CHAR(36), nullable=True, index=True)


class InvoiceCreate(BaseModel):
    object_levels_id: str | None = Field(default=None)
    num: str | None = Field(default=None)
    date: dt_date | None = Field(default=None)
    request_id: int | None = Field(default=None)
    file_id: str | None = Field(default=None)
    provider_id: str | None = Field(default=None)
    payer_id: str | None = Field(default=None)
    is_delivery_included: bool | None = Field(default=None)
    prepayment_percent: float | None = Field(default=None)
    due_days: int | None = Field(default=None)
    valid_until: int | None = Field(default=None)
    is_urgent: bool | None = Field(default=None)
    total_amount: float | None = Field(default=None)
    vat_rate: int | None = Field(default=None)
    vat_amount: float | None = Field(default=None)
    status: str | None = Field(default=None)


class InvoiceUpdate(BaseModel):
    object_levels_id: str | None = Field(default=None)
    num: str | None = Field(default=None)
    date: dt_date | None = Field(default=None)
    request_id: int | None = Field(default=None)
    file_id: str | None = Field(default=None)
    provider_id: str | None = Field(default=None)
    payer_id: str | None = Field(default=None)
    is_delivery_included: bool | None = Field(default=None)
    prepayment_percent: float | None = Field(default=None)
    due_days: int | None = Field(default=None)
    valid_until: int | None = Field(default=None)
    is_urgent: bool | None = Field(default=None)
    total_amount: float | None = Field(default=None)
    vat_rate: int | None = Field(default=None)
    vat_amount: float | None = Field(default=None)
    status: str | None = Field(default=None)


class InvoiceItemCreate(BaseModel):
    name: str | None = Field(default=None)
    unit_name: str | None = Field(default=None)
    quantity: float | None = Field(default=None)
    price: float | None = Field(default=None)
    sum: float | None = Field(default=None)
    nds: int | None = Field(default=None)
    value_nds: int | None = Field(default=None)
    unit_id: str | None = Field(default=None)
    converted_quantity: float | None = Field(default=None)


class InvoiceItemUpdate(BaseModel):
    name: str | None = Field(default=None)
    unit_name: str | None = Field(default=None)
    quantity: float | None = Field(default=None)
    price: float | None = Field(default=None)
    sum: float | None = Field(default=None)
    nds: int | None = Field(default=None)
    value_nds: int | None = Field(default=None)
    unit_id: str | None = Field(default=None)
    converted_quantity: float | None = Field(default=None)


class InvoiceParseRequest(BaseModel):
    file_path: str


class InvoiceLogCreate(BaseModel):
    user_id: str
    type: Literal["approval", "planing", "payment"] | None = Field(default=None)
    status_name: Literal["pending", "approved", "rejected"] | None = Field(default=None)
    date_response: datetime | None = Field(default=None)


class InvoiceLogUpdate(BaseModel):
    user_id: str | None = Field(default=None)
    type: Literal["approval", "planing", "payment"] | None = Field(default=None)
    status_name: Literal["pending", "approved", "rejected"] | None = Field(default=None)
    date_response: datetime | None = Field(default=None)


class InvoicePaymentCreate(BaseModel):
    value: float | None = Field(default=None)
    date_plan: dt_date | None = Field(default=None)
    paid: float | None = Field(default=None)
    paid_type: Literal["account", "cash", "mutual settlement", "by debit card"] | None = Field(default=None)
    paid_by: str | None = Field(default=None)
    paid_at: datetime | None = Field(default=None)
    file_id: str | None = Field(default=None)


class InvoicePaymentUpdate(BaseModel):
    value: float | None = Field(default=None)
    date_plan: dt_date | None = Field(default=None)
    paid: float | None = Field(default=None)
    paid_type: Literal["account", "cash", "mutual settlement", "by debit card"] | None = Field(default=None)
    paid_by: str | None = Field(default=None)
    paid_at: datetime | None = Field(default=None)
    file_id: str | None = Field(default=None)
