from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Column, DateTime, Float, ForeignKey, Integer, String

from app.database import SupplyBase


class UpdItemMapping(SupplyBase):
    __tablename__ = "upd_item_mapping"

    id = Column(CHAR(36), primary_key=True)
    upd_documents_id = Column(CHAR(36), ForeignKey("upd_documents.id"), nullable=True, index=True)
    upd_documents_item_id = Column(CHAR(36), ForeignKey("upd_documents_item.id"), nullable=True, index=True)
    nomenclature_id = Column(CHAR(36), ForeignKey("nomenclature.id"), nullable=True, index=True)
    group_number = Column(Integer, nullable=True)
    match_type = Column(String(20), nullable=True, default="direct")
    mapped_quantity = Column(Float, nullable=True)
    object_id = Column(CHAR(36), nullable=True, index=True)
    price = Column(Float, nullable=True)
    warehouse_id = Column(CHAR(36), nullable=True, index=True)
    attribute = Column(String(300), nullable=True, default="Закупка")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class UpdItemMappingCreate(BaseModel):
    upd_documents_id: str | None = Field(default=None)
    upd_documents_item_id: str | None = Field(default=None)
    nomenclature_id: str | None = Field(default=None)
    group_number: int | None = Field(default=None)
    match_type: Literal["direct"] | None = Field(default="direct")
    mapped_quantity: float | None = Field(default=None)
    object_id: str | None = Field(default=None)
    price: float | None = Field(default=None)
    warehouse_id: str | None = Field(default=None)
    attribute: str | None = Field(default="Закупка")


class UpdItemMappingUpdate(BaseModel):
    upd_documents_id: str | None = Field(default=None)
    upd_documents_item_id: str | None = Field(default=None)
    nomenclature_id: str | None = Field(default=None)
    group_number: int | None = Field(default=None)
    match_type: Literal["direct"] | None = Field(default=None)
    mapped_quantity: float | None = Field(default=None)
    object_id: str | None = Field(default=None)
    price: float | None = Field(default=None)
    warehouse_id: str | None = Field(default=None)
    attribute: str | None = Field(default=None)


class UpdItemMappingAutoMatchRequest(BaseModel):
    upd_documents_id: str
    warehouse_id: str | None = Field(default=None)
    object_id: str | None = Field(default=None)
    attribute: str | None = Field(default="Закупка")
