from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy import JSON, Column, DateTime, Integer, String, text

from app.database import SupplyBase


class SavedFilter(SupplyBase):
    __tablename__ = "saved_filters"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    page = Column(String(100), nullable=False)
    name = Column(String(300), nullable=False)
    filters = Column(JSON, nullable=False)
    is_default = Column(Integer, default=0)
    created_at = Column(DateTime, default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, nullable=True, default=None, onupdate=text("CURRENT_TIMESTAMP"))


class SavedFilterCreate(BaseModel):
    page: str = Field()
    name: str = Field()
    filters: dict = Field()
    is_default: int | None = Field(default=0)


class SavedFilterUpdate(BaseModel):
    page: str | None = Field(default=None)
    name: str | None = Field(default=None)
    filters: dict | None = Field(default=None)
    is_default: int | None = Field(default=None)
