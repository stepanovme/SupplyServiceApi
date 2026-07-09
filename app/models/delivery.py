from app.database import msk_now
import uuid
from datetime import date as dt_date
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text

from app.database import SupplyBase


class Delivery(SupplyBase):
    __tablename__ = "delivery"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    num = Column(Integer, nullable=True)
    request_id = Column(Integer, nullable=True, index=True)
    invoice_id = Column(Integer, nullable=True, index=True)
    carrier_id = Column(CHAR(36), nullable=False, index=True)
    pick_up_date = Column(Date, nullable=True)
    pick_up_date_planned = Column(Date, nullable=True)
    planned_delivery_from = Column(DateTime, nullable=True)
    planned_delivery_to = Column(DateTime, nullable=True)
    delivery_from = Column(CHAR(36), nullable=False, index=True)
    delivery_from_type = Column(String(20), nullable=True)
    delivery_to = Column(CHAR(36), nullable=False, index=True)
    delivery_to_type = Column(String(20), nullable=True)
    driver_id = Column(CHAR(36), nullable=False, index=True)
    status_id = Column(CHAR(36), ForeignKey("status.id"), nullable=False, index=True)
    comment = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)


class DeliveryItem(SupplyBase):
    __tablename__ = "delivery_items"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    delivery_id = Column(CHAR(36), ForeignKey("delivery.id"), nullable=False, index=True)
    nomenclature_id = Column(CHAR(36), nullable=True, index=True)
    request_item_id = Column(CHAR(36), nullable=True, index=True)
    invoice_item_id = Column(CHAR(36), nullable=True, index=True)
    name = Column(String(300), nullable=True)
    unit_name = Column(String(10), nullable=True)
    quantity = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)


class DeliveryCreate(BaseModel):
    num: int | None = Field(default=None)
    request_id: int | None = Field(default=None)
    invoice_id: int | None = Field(default=None)
    carrier_id: str | None = Field(default=None)
    pick_up_date: dt_date | None = Field(default=None)
    pick_up_date_planned: dt_date | None = Field(default=None)
    planned_delivery_from: datetime | None = Field(default=None)
    planned_delivery_to: datetime | None = Field(default=None)
    delivery_from: str | None = Field(default=None)
    delivery_from_type: Literal["company", "warehouse", "object"] | None = Field(default=None)
    delivery_to: str | None = Field(default=None)
    delivery_to_type: Literal["company", "warehouse", "object"] | None = Field(default=None)
    driver_id: str | None = Field(default=None)
    status_id: str | None = Field(default=None)
    comment: str | None = Field(default=None)


class DeliveryUpdate(BaseModel):
    num: int | None = Field(default=None)
    request_id: int | None = Field(default=None)
    invoice_id: int | None = Field(default=None)
    carrier_id: str | None = Field(default=None)
    pick_up_date: dt_date | None = Field(default=None)
    pick_up_date_planned: dt_date | None = Field(default=None)
    planned_delivery_from: datetime | None = Field(default=None)
    planned_delivery_to: datetime | None = Field(default=None)
    delivery_from: str | None = Field(default=None)
    delivery_from_type: Literal["company", "warehouse", "object"] | None = Field(default=None)
    delivery_to: str | None = Field(default=None)
    delivery_to_type: Literal["company", "warehouse", "object"] | None = Field(default=None)
    driver_id: str | None = Field(default=None)
    status_id: str | None = Field(default=None)
    comment: str | None = Field(default=None)


class DeliveryItemCreate(BaseModel):
    nomenclature_id: str | None = Field(default=None)
    request_item_id: str | None = Field(default=None)
    invoice_item_id: str | None = Field(default=None)
    name: str | None = Field(default=None)
    unit_name: str | None = Field(default=None)
    quantity: float | None = Field(default=None)


class DeliveryItemUpdate(BaseModel):
    nomenclature_id: str | None = Field(default=None)
    request_item_id: str | None = Field(default=None)
    invoice_item_id: str | None = Field(default=None)
    name: str | None = Field(default=None)
    unit_name: str | None = Field(default=None)
    quantity: float | None = Field(default=None)
