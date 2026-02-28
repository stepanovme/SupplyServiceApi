from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Column, DateTime, Float, ForeignKey, Integer, String, Text

from app.database import SupplyBase


class SupplyRequest(SupplyBase):
    __tablename__ = "request"

    id = Column(Integer, primary_key=True, autoincrement=True)
    object_levels_id = Column(CHAR(36), nullable=False, index=True)
    name = Column(String(200), nullable=True)
    comment = Column(Text, nullable=True)
    created_by = Column(CHAR(36), nullable=False, index=True)
    executor = Column(CHAR(36), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    deadline = Column(DateTime, nullable=True)
    status_id = Column(CHAR(36), ForeignKey("status.id"), nullable=False, index=True)


class RequestItem(SupplyBase):
    __tablename__ = "request_items"

    id = Column(CHAR(36), primary_key=True)
    request_id = Column(Integer, ForeignKey("request.id"), nullable=False, index=True)
    num = Column(Integer, nullable=False)
    nomenclature_id = Column(CHAR(36), nullable=True, index=True)
    name = Column(String(400), nullable=True)
    unit_id = Column(CHAR(36), nullable=True, index=True)
    quantity = Column(Float, nullable=False)
    warehouse_category_id = Column(CHAR(36), nullable=True, index=True)
    comment = Column(Text, nullable=True)


class RequestLog(SupplyBase):
    __tablename__ = "request_log"

    id = Column(CHAR(36), primary_key=True)
    user_id = Column(CHAR(36), nullable=False, index=True)
    request_id = Column(String(36), nullable=False, index=True)
    status_name = Column(String(20), nullable=False)
    date_response = Column(DateTime, nullable=True)


class StatusRef(SupplyBase):
    __tablename__ = "status"

    id = Column(CHAR(36), primary_key=True)
    name = Column(String(200), nullable=False)


class UnitRef(SupplyBase):
    __tablename__ = "unit"

    id = Column(CHAR(36), primary_key=True)
    name = Column(String(200), nullable=False)


class NomenclatureRef(SupplyBase):
    __tablename__ = "nomenclature"

    id = Column(CHAR(36), primary_key=True)
    warehouse_category_id = Column(CHAR(36), nullable=False, index=True)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    article = Column(String(200), nullable=True)
    unit_id = Column(CHAR(36), nullable=False, index=True)
    length = Column(Float, nullable=True)
    width = Column(Float, nullable=True)
    height = Column(Float, nullable=True)
    weight = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class WarehouseCategoryRef(SupplyBase):
    __tablename__ = "warehouse_category"

    id = Column(CHAR(36), primary_key=True)
    name = Column(String(200), nullable=False)
    parent_id = Column(CHAR(36), nullable=True, index=True)


class SupplyRequestCreate(BaseModel):
    object_levels_id: str | None = Field(default=None)
    name: str | None = Field(default=None)
    comment: str | None = Field(default=None)
    executor: str | None = Field(default=None)
    started_at: datetime | None = Field(default=None)
    approved_at: datetime | None = Field(default=None)
    rejected_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)
    deadline: datetime | None = Field(default=None)


class SupplyRequestUpdate(BaseModel):
    object_levels_id: str | None = Field(default=None)
    name: str | None = Field(default=None)
    comment: str | None = Field(default=None)
    executor: str | None = Field(default=None)
    started_at: datetime | None = Field(default=None)
    approved_at: datetime | None = Field(default=None)
    rejected_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)
    deadline: datetime | None = Field(default=None)
    status_id: str | None = Field(default=None)


class RequestItemCreate(BaseModel):
    num: int | None = Field(default=None)
    nomenclature_id: str | None = Field(default=None)
    name: str | None = Field(default=None)
    unit_id: str | None = Field(default=None)
    quantity: float | None = Field(default=1.0)
    warehouse_category_id: str | None = Field(default=None)
    comment: str | None = Field(default=None)


class RequestItemUpdate(BaseModel):
    num: int | None = Field(default=None)
    nomenclature_id: str | None = Field(default=None)
    name: str | None = Field(default=None)
    unit_id: str | None = Field(default=None)
    quantity: float | None = Field(default=None)
    warehouse_category_id: str | None = Field(default=None)
    comment: str | None = Field(default=None)
