from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Column, DateTime, String

from app.database import SupplyBase

HEX_COLOR_PATTERN = r"^#[0-9A-Fa-f]{6}$"


def msk_now():
    return datetime.utcnow() + timedelta(hours=3)


class ReceiptCategory(SupplyBase):
    """owner_user_id IS NULL - standard category (everybody can use it);
    otherwise a personal category of that user. (`scope_key`, a generated column that makes
    names unique per scope, exists only in the database.)"""

    __tablename__ = "receipt_categories"

    id = Column(CHAR(36), primary_key=True)
    name = Column(String(100), nullable=False)
    color = Column(String(7), nullable=True)
    owner_user_id = Column(String(36), nullable=True, index=True)
    created_by = Column(String(36), nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    updated_at = Column(DateTime, nullable=True)


class ReceiptCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str | None = Field(default=None, pattern=HEX_COLOR_PATTERN, description="Цвет #RRGGBB")
    is_system: bool = Field(
        default=False,
        description="true - стандартная категория для всех (только администратор); false - личная, видна только вам",
    )


class ReceiptCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    color: str | None = Field(default=None, pattern=HEX_COLOR_PATTERN, description="Цвет #RRGGBB; null - убрать цвет")
