from datetime import date as dt_date
from typing import Literal, Optional

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, BigInteger, Boolean, Column, DateTime, Date, Enum, Float, Integer, String, Text

from app.database import SupplyBase, msk_now
from app.models.object_ref import ObjectRef


class UpdRegistry(SupplyBase):
    """Реестр УПД (не путать с upd_documents - складскими УПД с позициями)."""
    __tablename__ = "upd_registry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    num = Column(String(100), nullable=True)
    date = Column(Date, nullable=True)
    sum = Column(Float(17, 2), nullable=True)
    buyer_id = Column(CHAR(36), nullable=True, index=True)
    seller_id = Column(CHAR(36), nullable=True, index=True)
    shipper_id = Column(CHAR(36), nullable=True, index=True)
    consignee_id = Column(CHAR(36), nullable=True, index=True)
    comment = Column(Text, nullable=True)
    is_signed = Column(Boolean, nullable=False, default=False)
    signed_at = Column(DateTime, nullable=True)
    signed_by = Column(CHAR(36), nullable=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(CHAR(36), nullable=True)


class UpdRegistryObject(SupplyBase):
    __tablename__ = "upd_registry_objects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    upd_id = Column(Integer, nullable=False, index=True)
    object_id = Column(CHAR(36), nullable=False, index=True)
    object_type = Column(Enum("object", "object_levels_id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False)


class UpdRegistryUserRole(SupplyBase):
    __tablename__ = "upd_registry_user_roles"

    id = Column(CHAR(36), primary_key=True)
    upd_id = Column(Integer, nullable=False, index=True)
    user_id = Column(CHAR(36), nullable=False, index=True)
    role = Column(Enum("creator", "executor", "co-executor", "observer"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False)


class UpdRegistryStatus(SupplyBase):
    __tablename__ = "upd_registry_statuses"

    id = Column(CHAR(36), primary_key=True)
    upd_id = Column(Integer, nullable=False, index=True)
    status_id = Column(CHAR(36), nullable=False)
    created_by = Column(CHAR(36), nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)


class UpdRegistryFolder(SupplyBase):
    __tablename__ = "upd_registry_folders"

    id = Column(CHAR(36), primary_key=True)
    upd_id = Column(Integer, nullable=False, index=True)
    name = Column(Text, nullable=False)
    parent_id = Column(CHAR(36), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(CHAR(36), nullable=True)


class UpdRegistryFile(SupplyBase):
    __tablename__ = "upd_registry_files"

    id = Column(CHAR(36), primary_key=True)
    upd_id = Column(Integer, nullable=False, index=True)
    original_name = Column(Text, nullable=False)
    storage_name = Column(Text, nullable=False)
    extension = Column(String(100), nullable=False)
    file_path = Column(Text, nullable=False)
    type = Column(Enum("original", "version"), nullable=False, default="original")
    uploaded_by = Column(CHAR(36), nullable=False)
    uploaded_at = Column(DateTime, nullable=False, default=msk_now)
    folder_id = Column(CHAR(36), nullable=True, index=True)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(CHAR(36), nullable=True)


class UpdRegistryLog(SupplyBase):
    __tablename__ = "upd_registry_logs"

    id = Column(CHAR(36), primary_key=True)
    seq = Column(BigInteger, autoincrement=True, unique=True)  # порядок записей внутри одной секунды
    upd_id = Column(Integer, nullable=False, index=True)
    user_id = Column(CHAR(36), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)


# --- Pydantic schemas ---

class UpdCreate(BaseModel):
    num: Optional[str] = Field(default=None, max_length=100, description="Номер УПД")
    date: Optional[dt_date] = Field(default=None, description="Дата УПД")
    sum: Optional[float] = Field(default=None, ge=0, description="Сумма УПД")
    buyer_id: Optional[str] = Field(default=None, description="Покупатель (контрагент)")
    seller_id: Optional[str] = Field(default=None, description="Продавец (контрагент)")
    shipper_id: Optional[str] = Field(default=None, description="Грузоотправитель (контрагент)")
    consignee_id: Optional[str] = Field(default=None, description="Грузополучатель (контрагент)")
    comment: Optional[str] = None
    is_signed: bool = Field(default=False, description="Подписан ли УПД")
    objects: list[ObjectRef] = Field(default_factory=list, description="Объекты УПД")


class UpdUpdate(BaseModel):
    num: Optional[str] = Field(default=None, max_length=100)
    date: Optional[dt_date] = None
    sum: Optional[float] = Field(default=None, ge=0)
    buyer_id: Optional[str] = None
    seller_id: Optional[str] = None
    shipper_id: Optional[str] = None
    consignee_id: Optional[str] = None
    comment: Optional[str] = None
    is_signed: Optional[bool] = Field(default=None, description="Подписан / не подписан")


class UpdObjectsAdd(BaseModel):
    objects: list[ObjectRef] = Field(min_length=1, max_length=100)


class UpdUserRoleCreate(BaseModel):
    user_id: str
    role: Literal["creator", "executor", "co-executor", "observer"]


class UpdUserRoleUpdate(BaseModel):
    role: Optional[Literal["creator", "executor", "co-executor", "observer"]] = None


class UpdStatusCreate(BaseModel):
    status_id: str


class UpdFolderCreate(BaseModel):
    upd_id: int
    name: str
    parent_id: Optional[str] = None


class UpdFolderUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[str] = None


class UpdFileUpdate(BaseModel):
    original_name: Optional[str] = None
    type: Optional[Literal["original", "version"]] = None
    folder_id: Optional[str] = None
