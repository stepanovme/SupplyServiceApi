from app.database import msk_now
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import CHAR, Column, DateTime, Float, ForeignKey, Integer, String, Text

from app.database import SupplyBase


class InvoiceOutgoing(SupplyBase):
    __tablename__ = "invoice_outgoing"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider_id = Column(CHAR(36), nullable=True, index=True)
    payer_id = Column(CHAR(36), nullable=True, index=True)
    num = Column(String(100), nullable=True)
    date = Column(DateTime, nullable=True)
    sum = Column(Float(17, 2), nullable=True)
    Ref_Key = Column(CHAR(36), nullable=True)
    created_at = Column(DateTime, nullable=True, default=msk_now)
    created_by = Column(CHAR(36), nullable=True, index=True)


class InvoiceOutgoingItem(SupplyBase):
    __tablename__ = "invoice_outgoing_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_outgoing = Column(Integer, ForeignKey("invoice_outgoing.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_outgoing_nomenclature_id = Column(CHAR(36), ForeignKey("invoice_outgoing_nomenclatures.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(Text, nullable=True)
    quantity = Column(Float(17, 8), nullable=True)
    price = Column(Float(17, 8), nullable=True)
    sum = Column(Float(17, 8), nullable=True)
    nds = Column(String(100), nullable=True)
    nds_sum = Column(Float(17, 8), nullable=True)
    created_at = Column(DateTime, nullable=True, default=msk_now)
    created_by = Column(CHAR(36), nullable=True, index=True)


class InvoiceOutgoingNomenclature(SupplyBase):
    __tablename__ = "invoice_outgoing_nomenclatures"

    id = Column(CHAR(36), primary_key=True)
    ref_key = Column(CHAR(36), nullable=True)
    name = Column(Text, nullable=False)
    invoice_outgoing_unit_id = Column(CHAR(36), ForeignKey("invoice_outgoing_units.id", ondelete="CASCADE"), nullable=True, index=True)
    created_at = Column(DateTime, nullable=True, default=msk_now)
    created_by = Column(CHAR(36), nullable=True, index=True)


class InvoiceOutgoingUnit(SupplyBase):
    __tablename__ = "invoice_outgoing_units"

    id = Column(CHAR(36), primary_key=True)
    ref_key = Column(CHAR(36), nullable=False)
    name = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=True, default=msk_now)
    created_by = Column(CHAR(36), nullable=True, index=True)


class InvoiceOutgoingCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    provider_id: str | None = Field(default=None)
    payer_id: str | None = Field(default=None)
    num: str | None = Field(default=None)
    date: datetime | None = Field(default=None)
    sum: float | None = Field(default=None)
    Ref_Key: str | None = Field(default=None)


class InvoiceOutgoingUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    provider_id: str | None = Field(default=None)
    payer_id: str | None = Field(default=None)
    num: str | None = Field(default=None)
    date: datetime | None = Field(default=None)
    sum: float | None = Field(default=None)
    Ref_Key: str | None = Field(default=None)


class InvoiceOutgoingItemCreate(BaseModel):
    invoice_outgoing_nomenclature_id: str | None = Field(default=None)
    name: str | None = Field(default=None)
    quantity: float | None = Field(default=None)
    price: float | None = Field(default=None)
    sum: float | None = Field(default=None)
    nds: str | None = Field(default=None)
    nds_sum: float | None = Field(default=None)


class InvoiceOutgoingItemUpdate(BaseModel):
    invoice_outgoing_nomenclature_id: str | None = Field(default=None)
    name: str | None = Field(default=None)
    quantity: float | None = Field(default=None)
    price: float | None = Field(default=None)
    sum: float | None = Field(default=None)
    nds: str | None = Field(default=None)
    nds_sum: float | None = Field(default=None)


class InvoiceOutgoingNomenclatureCreate(BaseModel):
    id: str
    ref_key: str | None = Field(default=None)
    name: str
    invoice_outgoing_unit_id: str | None = Field(default=None)


class InvoiceOutgoingNomenclatureUpdate(BaseModel):
    ref_key: str | None = Field(default=None)
    name: str | None = Field(default=None)
    invoice_outgoing_unit_id: str | None = Field(default=None)


class InvoiceOutgoingUnitCreate(BaseModel):
    id: str
    ref_key: str
    name: str


class InvoiceOutgoingUnitUpdate(BaseModel):
    ref_key: str | None = Field(default=None)
    name: str | None = Field(default=None)
