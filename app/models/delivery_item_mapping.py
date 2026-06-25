import uuid
from datetime import date as dt_date
from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Column, Date, DateTime, Float, ForeignKey, Integer

from app.database import SupplyBase


class DeliveryItemMapping(SupplyBase):
    __tablename__ = "delivery_item_mapping"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    delivery_id = Column(CHAR(36), ForeignKey("delivery.id"), nullable=False, index=True)
    delivery_item_id = Column(CHAR(36), ForeignKey("delivery_items.id"), nullable=False, index=True)
    nomenclature_id = Column(CHAR(36), nullable=True, index=True)
    delivery_at = Column(Date, nullable=True)
    delivery_quantity = Column(Float, nullable=True)
    nomenclature_quantity = Column(Float, nullable=True)
    group_number = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(CHAR(36), nullable=False, index=True)


class DeliveryItemMappingCreate(BaseModel):
    delivery_id: str
    delivery_item_id: str
    nomenclature_id: str | None = Field(default=None)
    delivery_at: dt_date | None = Field(default=None)
    delivery_quantity: float | None = Field(default=None)
    nomenclature_quantity: float | None = Field(default=None)
    group_number: int | None = Field(default=None)


class DeliveryItemMappingUpdate(BaseModel):
    delivery_id: str | None = Field(default=None)
    delivery_item_id: str | None = Field(default=None)
    nomenclature_id: str | None = Field(default=None)
    delivery_at: dt_date | None = Field(default=None)
    delivery_quantity: float | None = Field(default=None)
    nomenclature_quantity: float | None = Field(default=None)
    group_number: int | None = Field(default=None)


class DeliveryItemMappingAutoMatchRequest(BaseModel):
    delivery_id: str
