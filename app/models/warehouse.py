from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Column, String

from app.database import SupplyBase


class Warehouse(SupplyBase):
    __tablename__ = "warehouse"

    id = Column(CHAR(36), primary_key=True)
    name = Column(String(200), nullable=False)
    type = Column(String(30), nullable=True)
    object_levels_id = Column(CHAR(36), nullable=True)


class WarehouseCreate(BaseModel):
    name: str
    type: Literal["warehouse", "on-site warehouse"] | None = Field(default=None)
    object_levels_id: str | None = Field(default=None)


class WarehouseUpdate(BaseModel):
    name: str | None = Field(default=None)
    type: Literal["warehouse", "on-site warehouse"] | None = Field(default=None)
    object_levels_id: str | None = Field(default=None)
