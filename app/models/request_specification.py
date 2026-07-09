from __future__ import annotations
from app.database import msk_now

import uuid
from datetime import datetime, timedelta

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Column, DateTime, ForeignKey, Integer

from app.database import SupplyBase


class RequestSpecification(SupplyBase):
    __tablename__ = "request_specification"

    request_specification_id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id = Column(Integer, nullable=False, index=True)
    request_item_id = Column(CHAR(36), ForeignKey("request_items.id"), nullable=False, index=True)
    specification_id = Column(CHAR(36), nullable=False, index=True)
    specification_item_id = Column(CHAR(36), ForeignKey("specification_item.id"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)


class RequestSpecificationCreate(BaseModel):
    request_id: int
    request_item_id: str
    specification_id: str
    specification_item_id: str


class RequestSpecificationUpdate(BaseModel):
    request_id: int | None = Field(default=None)
    request_item_id: str | None = Field(default=None)
    specification_id: str | None = Field(default=None)
    specification_item_id: str | None = Field(default=None)


class RequestSpecificationResponse(BaseModel):
    request_specification_id: str
    request_id: int
    request_item_id: str
    specification_id: str
    specification_item_id: str
    specification_item_name: str | None = None
    created_at: datetime
    created_by: str
