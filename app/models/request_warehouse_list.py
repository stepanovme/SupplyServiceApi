from __future__ import annotations
from app.database import msk_now

import uuid
from datetime import datetime, timedelta

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Column, DateTime, Float, ForeignKey, Integer

from app.database import SupplyBase


class RequestWarehouseList(SupplyBase):
    __tablename__ = "request_warehouse_list"

    request_warehouse_list_id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id = Column(Integer, ForeignKey("request.id"), nullable=False, index=True)
    request_item_id = Column(CHAR(36), ForeignKey("request_items.id"), nullable=False, index=True)
    warehouse_id = Column(CHAR(36), ForeignKey("warehouse.id"), nullable=False, index=True)
    warehouse_list_id = Column(CHAR(36), ForeignKey("warehouse_list.id"), nullable=False, index=True)
    request_qantity = Column(Float, nullable=True)
    warehouse_quantity = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)


class RequestWarehouseListCreate(BaseModel):
    request_id: int
    request_item_id: str
    warehouse_id: str
    warehouse_list_id: str
    request_qantity: float | None = Field(default=None)
    warehouse_quantity: float | None = Field(default=None)


class RequestWarehouseListUpdate(BaseModel):
    request_id: int | None = Field(default=None)
    request_item_id: str | None = Field(default=None)
    warehouse_id: str | None = Field(default=None)
    warehouse_list_id: str | None = Field(default=None)
    request_qantity: float | None = Field(default=None)
    warehouse_quantity: float | None = Field(default=None)


class RequestWarehouseListResponse(BaseModel):
    request_warehouse_list_id: str
    request_id: int
    request_item_id: str
    warehouse_id: str
    warehouse_list_id: str
    request_qantity: float | None = None
    warehouse_quantity: float | None = None
    created_at: datetime
    created_by: str
