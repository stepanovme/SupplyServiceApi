import uuid
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Column, DateTime, Integer, String, Text

from app.database import SupplyBase


def msk_now():
    return datetime.utcnow() + timedelta(hours=3)


class BuhFolder(SupplyBase):
    __tablename__ = "buh_folder"

    id = Column(CHAR(36), primary_key=True)
    name = Column(Text, nullable=False)
    parent_id = Column(CHAR(36), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)


class BuhFile(SupplyBase):
    __tablename__ = "buh_file"

    id = Column(CHAR(36), primary_key=True)
    original_name = Column(Text, nullable=False)
    storage_name = Column(Text, nullable=False)
    extension = Column(String(100), nullable=True)
    mime_type = Column(String(200), nullable=True)
    file_size = Column(Integer, nullable=True)
    md5_hash = Column(String(32), nullable=True)
    file_path = Column(Text, nullable=False)
    folder_id = Column(CHAR(36), nullable=True, index=True)
    uploaded_by = Column(CHAR(36), nullable=False, index=True)
    uploaded_at = Column(DateTime, nullable=False, default=msk_now)


class BuhAccess(SupplyBase):
    __tablename__ = "buh_access"

    id = Column(CHAR(36), primary_key=True)
    user_id = Column(CHAR(36), nullable=True, index=True)
    department_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)


# --- Pydantic schemas ---


class BuhFolderCreate(BaseModel):
    name: str
    parent_id: str | None = Field(default=None)


class BuhFolderUpdate(BaseModel):
    name: str | None = Field(default=None)
    parent_id: str | None = Field(default=None)


class BuhAccessCreate(BaseModel):
    user_id: str | None = Field(default=None)
    department_id: int | None = Field(default=None)


class BuhFileUpdate(BaseModel):
    original_name: str | None = Field(default=None)
    folder_id: str | None = Field(default=None)
