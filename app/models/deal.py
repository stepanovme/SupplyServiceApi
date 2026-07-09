from app.database import msk_now
import uuid
from datetime import date as dt_date
from datetime import datetime, timedelta

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Column, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text

from app.database import SupplyBase


class Deal(SupplyBase):
    __tablename__ = "deals"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(300), nullable=True)
    object_id = Column(CHAR(36), nullable=True, index=True)
    counterparties_to = Column(CHAR(36), nullable=True, index=True)
    counterparties_from = Column(CHAR(36), nullable=True, index=True)
    status_id = Column(CHAR(36), ForeignKey("status.id"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)
    date = Column(Date, nullable=True)
    date_event = Column(Date, nullable=True)
    date_completed = Column(Date, nullable=True)
    payment_mode = Column(Enum("cash", "non-cash", name="payment_mode_enum"), nullable=False, default="cash")
    taxes = Column(Enum("agreement", "non-agreement", name="taxes_enum"), nullable=False, default="non-agreement")


class DealDelivery(SupplyBase):
    __tablename__ = "deal_delivery"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    deal_id = Column(CHAR(36), ForeignKey("deals.id"), nullable=False, index=True)
    type = Column(String(20), nullable=True)
    price_purchase = Column(Float, nullable=True)
    price = Column(Float, nullable=True)
    comment = Column(Text, nullable=True)


class DealProduct(SupplyBase):
    __tablename__ = "deal_products"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    deal_id = Column(CHAR(36), ForeignKey("deals.id"), nullable=False, index=True)
    nomenclature_id = Column(CHAR(36), ForeignKey("nomenclature.id"), nullable=False, index=True)
    warehouse_id = Column(CHAR(36), ForeignKey("warehouse.id"), nullable=False, index=True)
    vat_rate = Column(Integer, nullable=True)
    price_purchase = Column(Float, nullable=True)
    price = Column(Float, nullable=True)
    quantity = Column(Float, nullable=False)


class DealService(SupplyBase):
    __tablename__ = "deal_services"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    deal_id = Column(CHAR(36), ForeignKey("deals.id"), nullable=False, index=True)
    name = Column(Text, nullable=True)
    unit_name = Column(String(100), nullable=True)
    quantity = Column(Float, nullable=True)
    price_purchase = Column(Float, nullable=True)
    price = Column(Float, nullable=True)


class DealCreate(BaseModel):
    name: str | None = Field(default=None)
    object_id: str | None = Field(default=None)
    counterparties_to: str | None = Field(default=None)
    counterparties_from: str | None = Field(default=None)
    status_id: str | None = Field(default=None)
    date: dt_date | None = Field(default=None)
    date_event: dt_date | None = Field(default=None)
    date_completed: dt_date | None = Field(default=None)
    payment_mode: str | None = Field(default=None)
    taxes: str | None = Field(default=None)


class DealUpdate(BaseModel):
    name: str | None = Field(default=None)
    object_id: str | None = Field(default=None)
    counterparties_to: str | None = Field(default=None)
    counterparties_from: str | None = Field(default=None)
    status_id: str | None = Field(default=None)
    date: dt_date | None = Field(default=None)
    date_event: dt_date | None = Field(default=None)
    date_completed: dt_date | None = Field(default=None)
    payment_mode: str | None = Field(default=None)
    taxes: str | None = Field(default=None)


class DealDeliveryCreate(BaseModel):
    type: str | None = Field(default=None)
    price_purchase: float | None = Field(default=None)
    price: float | None = Field(default=None)
    comment: str | None = Field(default=None)


class DealDeliveryUpdate(BaseModel):
    type: str | None = Field(default=None)
    price_purchase: float | None = Field(default=None)
    price: float | None = Field(default=None)
    comment: str | None = Field(default=None)


class DealProductCreate(BaseModel):
    nomenclature_id: str
    warehouse_id: str
    vat_rate: int | None = Field(default=None)
    price_purchase: float | None = Field(default=None)
    price: float | None = Field(default=None)
    quantity: float


class DealProductUpdate(BaseModel):
    nomenclature_id: str | None = Field(default=None)
    warehouse_id: str | None = Field(default=None)
    vat_rate: int | None = Field(default=None)
    price_purchase: float | None = Field(default=None)
    price: float | None = Field(default=None)
    quantity: float | None = Field(default=None)


class DealServiceCreate(BaseModel):
    name: str | None = Field(default=None)
    unit_name: str | None = Field(default=None)
    quantity: float | None = Field(default=None)
    price_purchase: float | None = Field(default=None)
    price: float | None = Field(default=None)


class DealServiceUpdate(BaseModel):
    name: str | None = Field(default=None)
    unit_name: str | None = Field(default=None)
    quantity: float | None = Field(default=None)
    price_purchase: float | None = Field(default=None)
    price: float | None = Field(default=None)
