import uuid

from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Column, String

from app.database import SupplyBase


class Project(SupplyBase):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    object_id = Column(String(36), nullable=False, index=True)
    is_hide = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)


class ProjectCreate(BaseModel):
    id: str | None = Field(default=None)
    object_id: str = Field()
    is_hide: bool = Field(default=False)
    is_active: bool = Field(default=True)


class ProjectUpdate(BaseModel):
    is_hide: bool | None = Field(default=None)
    is_active: bool | None = Field(default=None)
