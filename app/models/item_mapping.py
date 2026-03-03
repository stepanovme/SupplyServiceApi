from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Column, DateTime, Float, ForeignKey, Integer, String

from app.database import SupplyBase


class ItemMapping(SupplyBase):
    __tablename__ = "item_mapping"

    id = Column(CHAR(36), primary_key=True)
    request_id = Column(Integer, ForeignKey("request.id"), nullable=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoice.id"), nullable=True, index=True)
    unit_id = Column(CHAR(36), nullable=True, index=True)
    request_item_id = Column(CHAR(36), ForeignKey("request_items.id"), nullable=False, index=True)
    invoice_item_id = Column(CHAR(36), ForeignKey("invoice_items.id"), nullable=False, index=True)
    group_number = Column(Integer, nullable=False)
    match_type = Column(String(20), nullable=False, default="direct")
    mapped_quantity = Column(Float, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ItemMappingCreate(BaseModel):
    request_id: int | None = Field(default=None)
    invoice_id: int | None = Field(default=None)
    unit_id: str | None = Field(default=None)
    request_item_id: str
    invoice_item_id: str
    group_number: int
    match_type: Literal["direct", "sum", "kit_head", "kit_component"] = Field(default="direct")
    mapped_quantity: float = Field(default=0)


class ItemMappingUpdate(BaseModel):
    request_id: int | None = Field(default=None)
    invoice_id: int | None = Field(default=None)
    unit_id: str | None = Field(default=None)
    request_item_id: str | None = Field(default=None)
    invoice_item_id: str | None = Field(default=None)
    group_number: int | None = Field(default=None)
    match_type: Literal["direct", "sum", "kit_head", "kit_component"] | None = Field(default=None)
    mapped_quantity: float | None = Field(default=None)


class ItemMappingAutoMatchRequest(BaseModel):
    request_id: int
    invoice_id: int
