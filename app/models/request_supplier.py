from __future__ import annotations
from app.database import msk_now

import uuid
from datetime import date as dt_date
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, Boolean

from app.database import SupplyBase


class RequestSupplier(SupplyBase):
    __tablename__ = "request_supplier"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id = Column(Integer, ForeignKey("request.id"), nullable=False, index=True)
    payer_id = Column(CHAR(36), nullable=True, index=True)
    recipient_id = Column(CHAR(36), nullable=True, index=True)
    delivery_required = Column(Boolean, nullable=True)
    delivery_date = Column(Date, nullable=True)
    days_delay = Column(Integer, nullable=True)
    deadline = Column(DateTime, nullable=True)
    project_levels_id = Column(CHAR(36), nullable=True, index=True)
    delivery_to = Column(CHAR(36), nullable=True, index=True)
    delivery_to_type = Column(String(20), nullable=True)
    comment_request = Column(Text, nullable=True)
    comment_supplier = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    sent_at = Column(DateTime, nullable=True)
    created_by = Column(CHAR(36), nullable=False, index=True)
    sent_by = Column(CHAR(36), nullable=True, index=True)
    status_id = Column(CHAR(36), ForeignKey("status.id"), nullable=True, index=True)


class RequestSupplierItem(SupplyBase):
    __tablename__ = "request_supplier_items"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    request_supplier_id = Column(CHAR(36), ForeignKey("request_supplier.id"), nullable=False, index=True)
    name = Column(Text, nullable=False)
    unit_name = Column(String(100), nullable=False)
    quantity = Column(Float, nullable=False)
    comment = Column(Text, nullable=True)


class RequestSupplierEmailSender(SupplyBase):
    __tablename__ = "request_supplier_email_sender"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    request_supplier_id = Column(CHAR(36), ForeignKey("request_supplier.id"), nullable=False, index=True)
    smtp_id = Column(CHAR(36), ForeignKey("smtp.id"), nullable=False, index=True)
    email = Column(String(300), nullable=True)


class RequestSupplierFile(SupplyBase):
    __tablename__ = "request_supplier_files"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    request_supplier_id = Column(CHAR(36), ForeignKey("request_supplier.id"), nullable=False, index=True)
    original_name = Column(Text, nullable=False)
    storage_name = Column(Text, nullable=False)
    file_path = Column(Text, nullable=False)
    uploaded_by = Column(CHAR(36), nullable=False, index=True)
    uploaded_at = Column(DateTime, nullable=False, default=msk_now)


class RequestSupplierRecipient(SupplyBase):
    __tablename__ = "request_supplier_recipient"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    request_supplier_id = Column("request_supplier", CHAR(36), ForeignKey("request_supplier.id"), nullable=False, index=True)
    email = Column(Text, nullable=True)
    fio = Column(Text, nullable=True)
    company_name = Column(Text, nullable=True)


class RequestSupplierLink(SupplyBase):
    __tablename__ = "request_supplier_links"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    request_supplier_id = Column(CHAR(36), ForeignKey("request_supplier.id"), nullable=False, index=True)
    request_supplier_recipient_id = Column(CHAR(36), ForeignKey("request_supplier_recipient.id"), nullable=False, index=True)
    code = Column(String(10), nullable=False)
    status = Column(String(10), nullable=False, default="active")
    created_at = Column(DateTime, nullable=False, default=msk_now)
    updated_at = Column(DateTime, nullable=True)


class RequestSupplierCreate(BaseModel):
    request_id: int
    payer_id: str | None = Field(default=None)
    recipient_id: str | None = Field(default=None)
    delivery_required: bool | None = Field(default=None)
    delivery_date: dt_date | None = Field(default=None)
    days_delay: int | None = Field(default=None)
    deadline: datetime | None = Field(default=None)
    project_levels_id: str | None = Field(default=None)
    delivery_to: str | None = Field(default=None)
    delivery_to_type: Literal["project", "warehouse"] | None = Field(default=None)
    comment_request: str | None = Field(default=None)
    comment_supplier: str | None = Field(default=None)
    sent_at: datetime | None = Field(default=None)
    sent_by: str | None = Field(default=None)
    status_id: str | None = Field(default=None)


class RequestSupplierUpdate(BaseModel):
    request_id: int | None = Field(default=None)
    payer_id: str | None = Field(default=None)
    recipient_id: str | None = Field(default=None)
    delivery_required: bool | None = Field(default=None)
    delivery_date: dt_date | None = Field(default=None)
    days_delay: int | None = Field(default=None)
    deadline: datetime | None = Field(default=None)
    project_levels_id: str | None = Field(default=None)
    delivery_to: str | None = Field(default=None)
    delivery_to_type: Literal["project", "warehouse"] | None = Field(default=None)
    comment_request: str | None = Field(default=None)
    comment_supplier: str | None = Field(default=None)
    sent_at: datetime | None = Field(default=None)
    sent_by: str | None = Field(default=None)
    status_id: str | None = Field(default=None)


class RequestSupplierItemCreate(BaseModel):
    name: str
    unit_name: str
    quantity: float
    comment: str | None = Field(default=None)


class RequestSupplierItemUpdate(BaseModel):
    name: str | None = Field(default=None)
    unit_name: str | None = Field(default=None)
    quantity: float | None = Field(default=None)
    comment: str | None = Field(default=None)


class RequestSupplierEmailSenderCreate(BaseModel):
    smtp_id: str
    email: str | None = Field(default=None)


class RequestSupplierEmailSenderUpdate(BaseModel):
    smtp_id: str | None = Field(default=None)
    email: str | None = Field(default=None)


class RequestSupplierFileCreate(BaseModel):
    original_name: str
    storage_name: str
    file_path: str
    uploaded_by: str


class RequestSupplierFileUpdate(BaseModel):
    original_name: str | None = Field(default=None)
    storage_name: str | None = Field(default=None)
    file_path: str | None = Field(default=None)
    uploaded_by: str | None = Field(default=None)


class RequestSupplierRecipientCreate(BaseModel):
    email: str | None = Field(default=None)
    fio: str | None = Field(default=None)
    company_name: str | None = Field(default=None)


class RequestSupplierRecipientUpdate(BaseModel):
    email: str | None = Field(default=None)
    fio: str | None = Field(default=None)
    company_name: str | None = Field(default=None)


class RequestSupplierLinkCreate(BaseModel):
    request_supplier_recipient_id: str
    code: str | None = Field(default=None)
    status: Literal["active", "inactive"] = Field(default="active")


class RequestSupplierLinkUpdate(BaseModel):
    request_supplier_recipient_id: str | None = Field(default=None)
    code: str | None = Field(default=None)
    status: Literal["active", "inactive"] | None = Field(default=None)


class RequestSupplierLinkResponse(BaseModel):
    id: str
    request_supplier_id: str
    request_supplier_recipient_id: str
    code: str
    status: Literal["active", "inactive"]
    created_at: datetime
    updated_at: datetime | None = None


class RequestSupplierSendResponse(BaseModel):
    request_supplier_id: str
    sender_count: int
    recipient_count: int
    sent_count: int
    skipped_count: int


class RequestSupplierTestSmtpResponse(BaseModel):
    request_supplier_id: str
    sender_count: int
    success_count: int
    failed_count: int
    results: list[dict]
