from datetime import date as dt_date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Column, DateTime, Date, Enum, Float, Integer, String, Text

from app.database import SupplyBase, msk_now
from app.models.object_ref import ObjectRef


class ActType(SupplyBase):
    __tablename__ = "act_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(300), nullable=False)
    created_at = Column(DateTime, nullable=False)
    created_by = Column(CHAR(36), nullable=False)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(CHAR(36), nullable=True)


class Act(SupplyBase):
    __tablename__ = "acts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    act_type_id = Column(Integer, nullable=False, index=True)
    num = Column(String(100), nullable=False)
    date = Column(Date, nullable=True)
    sum = Column(Float(17, 2), nullable=True)
    comment = Column(Text, nullable=True)
    object_id = Column(String(36), nullable=True)
    object_type = Column(Enum("object", "object_levels_id"), nullable=True)
    customer_id = Column(CHAR(36), nullable=False, index=True)
    contractor_id = Column(CHAR(36), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)


class ActObject(SupplyBase):
    __tablename__ = "act_objects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    act_id = Column(Integer, nullable=False, index=True)
    object_id = Column(CHAR(36), nullable=False, index=True)
    object_type = Column(Enum("object", "object_levels_id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False)


class ActFolder(SupplyBase):
    __tablename__ = "act_folders"

    id = Column(CHAR(36), primary_key=True)
    act_id = Column(Integer, nullable=False, index=True)
    name = Column(Text, nullable=False)
    parent_id = Column(CHAR(36), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(CHAR(36), nullable=True)


class ActFile(SupplyBase):
    __tablename__ = "act_files"

    id = Column(CHAR(36), primary_key=True)
    act_id = Column(Integer, nullable=False, index=True)
    original_name = Column(Text, nullable=False)
    storage_name = Column(Text, nullable=False)
    extension = Column(String(100), nullable=False)
    file_path = Column(Text, nullable=False)
    type = Column(Enum("original", "version"), nullable=False)
    uploaded_by = Column(CHAR(36), nullable=False, index=True)
    uploaded_at = Column(DateTime, nullable=False, default=msk_now)
    act_folder_id = Column(CHAR(36), nullable=True, index=True)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(CHAR(36), nullable=True)


class ActStatus(SupplyBase):
    __tablename__ = "act_status"

    id = Column(CHAR(36), primary_key=True)
    act_id = Column(Integer, nullable=False, index=True)
    status_id = Column(CHAR(36), nullable=False, index=True)
    created_by = Column(CHAR(36), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)


class ActUserRole(SupplyBase):
    __tablename__ = "act_user_roles"

    id = Column(CHAR(36), primary_key=True)
    act_id = Column(Integer, nullable=False, index=True)
    user_id = Column(CHAR(36), nullable=False, index=True)
    role = Column(Enum("creator", "executor", "co-executor", "observer"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)


# --- Pydantic schemas ---

class ActTypeResponse(BaseModel):
    id: int
    name: str


class ActTypeCreate(BaseModel):
    name: str


class ActCreate(BaseModel):
    act_type_id: int
    num: str
    date: Optional[dt_date] = Field(default=None)
    sum: Optional[float] = Field(default=None)
    comment: Optional[str] = Field(default=None, description="Комментарий к акту")
    object_id: Optional[str] = Field(default=None)
    object_type: Optional[Literal["object", "object_levels_id"]] = Field(default=None)
    objects: list[ObjectRef] = Field(
        default_factory=list,
        description="Несколько объектов акта. object_id/object_type по-прежнему можно передать - это основной объект.",
    )
    customer_id: str
    contractor_id: str


class ActObjectsAdd(BaseModel):
    objects: list[ObjectRef] = Field(min_length=1, max_length=100)


class ActUpdate(BaseModel):
    act_type_id: Optional[int] = None
    num: Optional[str] = None
    date: Optional[dt_date] = Field(default=None)
    sum: Optional[float] = None
    comment: Optional[str] = Field(default=None, description="Комментарий к акту; null - убрать")
    object_id: Optional[str] = None
    object_type: Optional[Literal["object", "object_levels_id"]] = None
    customer_id: Optional[str] = None
    contractor_id: Optional[str] = None


class ActUserRoleCreate(BaseModel):
    user_id: str
    role: Literal["creator", "executor", "co-executor", "observer"]


class ActUserRoleUpdate(BaseModel):
    role: Optional[Literal["creator", "executor", "co-executor", "observer"]] = None


class ActStatusCreate(BaseModel):
    status_id: str


class ActFolderCreate(BaseModel):
    act_id: int
    name: str
    parent_id: Optional[str] = None


class ActFolderUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[str] = None


class ActFileUpdate(BaseModel):
    type: Optional[Literal["original", "version"]] = None
    act_folder_id: Optional[str] = None
