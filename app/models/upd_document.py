from app.database import msk_now
from datetime import date as dt_date
from datetime import datetime, timedelta

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text

from app.database import SupplyBase


class UpdDocument(SupplyBase):
    __tablename__ = "upd_documents"

    id = Column(CHAR(36), primary_key=True)
    warehouse_id = Column(CHAR(36), nullable=True, index=True)
    provider_id = Column(CHAR(36), nullable=True, index=True)
    payer_id = Column(CHAR(36), nullable=True, index=True)
    file_id = Column(CHAR(36), nullable=True, index=True)
    num = Column(String(100), nullable=True)
    date = Column(Date, nullable=True)
    status = Column(CHAR(36), ForeignKey("status.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)


class UpdDocumentItem(SupplyBase):
    __tablename__ = "upd_documents_item"

    id = Column(CHAR(36), primary_key=True)
    upd_documents_id = Column(CHAR(36), ForeignKey("upd_documents.id"), nullable=False, index=True)
    position = Column(Integer, nullable=True)
    name = Column(Text, nullable=True)
    unit_name = Column(String(30), nullable=True)
    quantity = Column(Float, nullable=True)
    vat_rate = Column(Integer, nullable=True)
    price = Column(Float, nullable=True)
    sum = Column(Float, nullable=True)


class UpdDocumentCreate(BaseModel):
    warehouse_id: str | None = Field(default=None)
    provider_id: str | None = Field(default=None)
    payer_id: str | None = Field(default=None)
    num: str | None = Field(default=None)
    date: dt_date | None = Field(default=None)
    status: str | None = Field(default=None)


class UpdDocumentUpdate(BaseModel):
    warehouse_id: str | None = Field(default=None)
    provider_id: str | None = Field(default=None)
    payer_id: str | None = Field(default=None)
    num: str | None = Field(default=None)
    date: dt_date | None = Field(default=None)
    status: str | None = Field(default=None)


class UpdDocumentItemCreate(BaseModel):
    position: int | None = Field(default=None)
    name: str | None = Field(default=None)
    unit_name: str | None = Field(default=None)
    quantity: float | None = Field(default=None)
    vat_rate: int | None = Field(default=None)
    price: float | None = Field(default=None)
    sum: float | None = Field(default=None)


class UpdDocumentItemUpdate(BaseModel):
    position: int | None = Field(default=None)
    name: str | None = Field(default=None)
    unit_name: str | None = Field(default=None)
    quantity: float | None = Field(default=None)
    vat_rate: int | None = Field(default=None)
    price: float | None = Field(default=None)
    sum: float | None = Field(default=None)
