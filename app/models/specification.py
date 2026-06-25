from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Column, DateTime, ForeignKey, Float, Integer, Text

from app.database import SupplyBase


DEFAULT_SPECIFICATION_STATUS_ID = "ff28c5a3-1968-11f1-aa8c-bc241127d0bd"


class Specification(SupplyBase):
    __tablename__ = "specification"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(Text, nullable=True)
    comment = Column(Text, nullable=True)
    object_levels_id = Column(CHAR(36), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(CHAR(36), nullable=False, index=True)
    status_id = Column(CHAR(36), ForeignKey("status.id"), nullable=True, index=True)


class SpecificationFile(SupplyBase):
    __tablename__ = "specification_files"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    specification_id = Column(CHAR(36), ForeignKey("specification.id"), nullable=False, index=True)
    original_name = Column(Text, nullable=False)
    storage_name = Column(Text, nullable=False)
    file_path = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(CHAR(36), nullable=False, index=True)


class SpecificationItem(SupplyBase):
    __tablename__ = "specification_item"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    specification_id = Column(CHAR(36), ForeignKey("specification.id"), nullable=False, index=True)
    num = Column(Integer, nullable=False)
    section_name = Column(Text, nullable=True)
    name = Column(Text, nullable=True)
    nomenclature_id = Column(CHAR(36), nullable=True, index=True)
    unit_name = Column(Text, nullable=True)
    unit_id = Column(CHAR(36), nullable=True, index=True)
    quantity = Column(Float, nullable=True)
    price = Column(Float, nullable=True)
    sum = Column(Float, nullable=True)
    warehouse_category_name = Column(Text, nullable=True)
    warehouse_category_id = Column(CHAR(36), nullable=True, index=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(CHAR(36), nullable=False, index=True)


class SpecificationCreate(BaseModel):
    name: str | None = Field(default=None)
    comment: str | None = Field(default=None)
    object_levels_id: str | None = Field(default=None)
    status_id: str | None = Field(default=None)


class SpecificationUpdate(BaseModel):
    name: str | None = Field(default=None)
    comment: str | None = Field(default=None)
    object_levels_id: str | None = Field(default=None)
    status_id: str | None = Field(default=None)


class SpecificationFileCreate(BaseModel):
    original_name: str
    storage_name: str
    file_path: str
    created_by: str


class SpecificationFileUpdate(BaseModel):
    original_name: str | None = Field(default=None)
    storage_name: str | None = Field(default=None)
    file_path: str | None = Field(default=None)
    created_by: str | None = Field(default=None)


class SpecificationItemCreate(BaseModel):
    num: int | None = Field(default=None)
    section_name: str | None = Field(default=None)
    name: str | None = Field(default=None)
    nomenclature_id: str | None = Field(default=None)
    unit_name: str | None = Field(default=None)
    unit_id: str | None = Field(default=None)
    quantity: float | None = Field(default=None)
    price: float | None = Field(default=None)
    sum: float | None = Field(default=None)
    warehouse_category_name: str | None = Field(default=None)
    warehouse_category_id: str | None = Field(default=None)
    comment: str | None = Field(default=None)


class SpecificationItemUpdate(BaseModel):
    num: int | None = Field(default=None)
    section_name: str | None = Field(default=None)
    name: str | None = Field(default=None)
    nomenclature_id: str | None = Field(default=None)
    unit_name: str | None = Field(default=None)
    unit_id: str | None = Field(default=None)
    quantity: float | None = Field(default=None)
    price: float | None = Field(default=None)
    sum: float | None = Field(default=None)
    warehouse_category_name: str | None = Field(default=None)
    warehouse_category_id: str | None = Field(default=None)
    comment: str | None = Field(default=None)


class SpecificationResponse(BaseModel):
    id: str
    name: str | None = None
    comment: str | None = None
    object_levels_id: str | None = None
    project_name: str | None = None
    created_at: datetime
    created_by: str
    created_by_user: str | None = None
    status_id: str | None = None
    status_name: str | None = None
    files: list[dict] = Field(default_factory=list)


class SpecificationFileResponse(BaseModel):
    id: str
    specification_id: str
    original_name: str
    storage_name: str
    file_path: str
    created_at: datetime
    created_by: str
    created_by_user: str | None = None


class SpecificationSummaryResponse(BaseModel):
    specification_item_id: str
    specification_item_name: str | None = None
    ordered_quantity: float = 0
    warehouse_quantity: float = 0


class SpecificationItemResponse(BaseModel):
    id: str
    specification_id: str
    num: int
    section_name: str | None = None
    name: str | None = None
    nomenclature_id: str | None = None
    unit_name: str | None = None
    unit_id: str | None = None
    quantity: float | None = None
    price: float | None = None
    sum: float | None = None
    warehouse_category_name: str | None = None
    warehouse_category_id: str | None = None
    comment: str | None = None
    created_at: datetime
    created_by: str
    created_by_user: str | None = None
