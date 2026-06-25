from datetime import date as dt_date
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import Boolean, CHAR, Column, Date, Float, ForeignKey, Integer, String, Text

from app.database import SupplyBase


class Warehouse(SupplyBase):
    __tablename__ = "warehouse"

    id = Column(CHAR(36), primary_key=True)
    name = Column(String(200), nullable=False)
    type = Column(String(30), nullable=True)
    object_levels_id = Column(CHAR(36), nullable=True)


class WarehouseList(SupplyBase):
    __tablename__ = "warehouse_list"

    id = Column(CHAR(36), primary_key=True)
    nomenclature_id = Column(CHAR(36), nullable=False, index=True)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=True)
    vat_rate = Column(Integer, nullable=True)
    upd_item_mapping_id = Column(CHAR(36), nullable=True, index=True)
    attribute = Column(Text, nullable=True)
    date = Column(Date, nullable=False)
    object_levels_id = Column(CHAR(36), nullable=True, index=True)
    object_id = Column(CHAR(36), nullable=True, index=True)
    delivery_id = Column(CHAR(36), nullable=True, index=True)
    warehouse_receipt_id = Column(CHAR(36), ForeignKey("warehouse_receipt.id"), nullable=True, index=True)
    toll = Column(Boolean, nullable=False, default=False)
    toll_company_id = Column(CHAR(36), nullable=True, index=True)
    warehouse_id = Column(CHAR(36), nullable=False, index=True)


class WarehouseCreate(BaseModel):
    name: str
    type: Literal["warehouse", "on-site warehouse"] | None = Field(default=None)
    object_levels_id: str | None = Field(default=None)


class WarehouseUpdate(BaseModel):
    name: str | None = Field(default=None)
    type: Literal["warehouse", "on-site warehouse"] | None = Field(default=None)
    object_levels_id: str | None = Field(default=None)


class WarehouseListCreate(BaseModel):
    nomenclature_id: str
    quantity: float
    price: float | None = Field(default=None)
    vat_rate: int | None = Field(default=None)
    upd_item_mapping_id: str | None = Field(default=None)
    attribute: str | None = Field(default=None)
    date: dt_date
    object_levels_id: str | None = Field(default=None)
    object_id: str | None = Field(default=None)
    delivery_id: str | None = Field(default=None)
    warehouse_receipt_id: str | None = Field(default=None)
    toll: bool | None = Field(default=False)
    toll_company_id: str | None = Field(default=None)


class WarehouseListUpdate(BaseModel):
    nomenclature_id: str | None = Field(default=None)
    quantity: float | None = Field(default=None)
    price: float | None = Field(default=None)
    vat_rate: int | None = Field(default=None)
    upd_item_mapping_id: str | None = Field(default=None)
    attribute: str | None = Field(default=None)
    date: dt_date | None = Field(default=None)
    object_levels_id: str | None = Field(default=None)
    object_id: str | None = Field(default=None)
    delivery_id: str | None = Field(default=None)
    warehouse_receipt_id: str | None = Field(default=None)
    toll: bool | None = Field(default=None)
    toll_company_id: str | None = Field(default=None)
