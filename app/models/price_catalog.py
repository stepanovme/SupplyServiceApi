from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Column, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text

from app.database import SupplyBase, msk_now
from app.models.estimate import RESOURCE_TYPES, ResourceType

CatalogKind = Literal["works", "resources"]


class PriceWorkFolder(SupplyBase):
    __tablename__ = "price_work_folders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    parent_id = Column(Integer, ForeignKey("price_work_folders.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False)


class PriceWorkItem(SupplyBase):
    __tablename__ = "price_work_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    folder_id = Column(Integer, ForeignKey("price_work_folders.id", ondelete="CASCADE"), nullable=True, index=True)
    code = Column(String(100), nullable=True)
    name = Column(String(500), nullable=False)
    unit_name = Column(String(50), nullable=True)
    quantity = Column(Numeric(18, 4), nullable=False, default=0)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(CHAR(36), nullable=True)


class PriceWorkItemResource(SupplyBase):
    """Ресурс в составе работы справочника (шаблон: в смету копируется вместе с работой)."""
    __tablename__ = "price_work_item_resources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(Integer, ForeignKey("price_work_items.id", ondelete="CASCADE"), nullable=False, index=True)
    position = Column(Integer, nullable=False)
    type = Column(Enum(*RESOURCE_TYPES, name="price_work_resource_type"), nullable=False)
    name = Column(String(255), nullable=False)
    contractor_id = Column(CHAR(36), nullable=True)
    quantity = Column(Numeric(18, 4), nullable=False, default=0)
    unit_name = Column(String(50), nullable=True)
    unit_price = Column(Numeric(18, 2), nullable=False, default=0)
    markup_percent = Column(Numeric(9, 2), nullable=False, default=0)


class PriceResourceFolder(SupplyBase):
    __tablename__ = "price_resource_folders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    parent_id = Column(Integer, ForeignKey("price_resource_folders.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False)


class PriceResourceItem(SupplyBase):
    __tablename__ = "price_resource_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    folder_id = Column(Integer, ForeignKey("price_resource_folders.id", ondelete="CASCADE"), nullable=True, index=True)
    type = Column(Enum(*RESOURCE_TYPES, name="price_resource_type"), nullable=False)
    code = Column(String(100), nullable=True)
    name = Column(String(500), nullable=False)
    unit_name = Column(String(50), nullable=True)
    price = Column(Numeric(18, 2), nullable=False, default=0)
    contractor_id = Column(CHAR(36), nullable=True, index=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(CHAR(36), nullable=True)


# --- schemas ---
class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    parent_id: int | None = Field(default=None, description="null - папка в корне")


class FolderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    parent_id: int | None = Field(default=None, description="Куда перенести; null - в корень")


class TemplateResourceCreate(BaseModel):
    type: ResourceType
    name: str = Field(min_length=1, max_length=255)
    contractor_id: str | None = None
    quantity: Decimal = Field(default=Decimal(0), ge=0)
    unit_name: str | None = Field(default=None, max_length=50)
    unit_price: Decimal = Field(default=Decimal(0), ge=0)
    markup_percent: Decimal = Field(default=Decimal(0), ge=0)
    position: int | None = Field(default=None, ge=1)


class TemplateResourceUpdate(BaseModel):
    type: ResourceType | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    contractor_id: str | None = None
    quantity: Decimal | None = Field(default=None, ge=0)
    unit_name: str | None = Field(default=None, max_length=50)
    unit_price: Decimal | None = Field(default=None, ge=0)
    markup_percent: Decimal | None = Field(default=None, ge=0)
    position: int | None = Field(default=None, ge=1)


class PriceItemCreate(BaseModel):
    folder_id: int | None = Field(default=None, description="null - позиция в корне")
    name: str = Field(min_length=1, max_length=500)
    unit_name: str | None = Field(default=None, max_length=50)
    quantity: Decimal | None = Field(default=None, ge=0, description="Только для справочника работ: объём работы")
    price: Decimal | None = Field(default=None, ge=0, description="Только для справочника ресурсов (по умолчанию 0)")
    comment: str | None = None
    type: ResourceType | None = Field(default=None, description="Только для справочника ресурсов (обязательно)")
    contractor_id: str | None = Field(default=None, description="Только для справочника ресурсов")
    resources: list[TemplateResourceCreate] = Field(default_factory=list, description="Только для справочника работ: состав работы")


class PriceItemUpdate(BaseModel):
    folder_id: int | None = Field(default=None, description="Перенести в папку; null - в корень")
    name: str | None = Field(default=None, min_length=1, max_length=500)
    unit_name: str | None = Field(default=None, max_length=50)
    quantity: Decimal | None = Field(default=None, ge=0, description="Только для справочника работ")
    price: Decimal | None = Field(default=None, ge=0, description="Только для справочника ресурсов")
    comment: str | None = None
    type: ResourceType | None = None
    contractor_id: str | None = None
