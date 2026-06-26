import uuid
from datetime import date as dt_date
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Column, Date, DateTime, Enum, Float, Integer, String, Text

from app.database import SupplyBase


class Contract(SupplyBase):
    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    num = Column(String(100), nullable=True)
    internal_num = Column(String(100), nullable=True)
    date = Column(Date, nullable=True)
    document_type_id = Column(CHAR(36), nullable=False, index=True)
    name = Column(Text, nullable=True)
    date_start = Column(Date, nullable=True)
    date_end = Column(Date, nullable=True)
    date_completed = Column(Date, nullable=True)
    customer_id = Column(CHAR(36), nullable=False, index=True)
    contractor_id = Column(CHAR(36), nullable=False, index=True)
    type = Column(Enum("provider", "buyer"), nullable=False)
    sum = Column(Float(17, 8), nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True)
    created_by = Column(CHAR(36), nullable=False, index=True)


class ContractFolder(SupplyBase):
    __tablename__ = "contract_folders"

    id = Column(CHAR(36), primary_key=True)
    contract_id = Column(Integer, nullable=False, index=True)
    name = Column(Text, nullable=False)
    parent_id = Column(CHAR(36), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(CHAR(36), nullable=False, index=True)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(CHAR(36), nullable=True, index=True)


class ContractFile(SupplyBase):
    __tablename__ = "contract_files"

    id = Column(CHAR(36), primary_key=True)
    contract_id = Column(Integer, nullable=False, index=True)
    original_name = Column(Text, nullable=False)
    storage_name = Column(Text, nullable=False)
    extension = Column(String(100), nullable=True)
    file_path = Column(Text, nullable=False)
    uploaded_by = Column(CHAR(36), nullable=False, index=True)
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    contract_folder_id = Column(CHAR(36), nullable=True, index=True)
    type = Column(Enum("original", "version"), nullable=True)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(CHAR(36), nullable=True, index=True)


class ContractWorkType(SupplyBase):
    __tablename__ = "contract_work_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(CHAR(36), nullable=False, index=True)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(CHAR(36), nullable=True, index=True)


class DocumentType(SupplyBase):
    __tablename__ = "document_type"

    id = Column(CHAR(36), primary_key=True)
    name = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(CHAR(36), nullable=False, index=True)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(CHAR(36), nullable=True, index=True)


class ContractLog(SupplyBase):
    __tablename__ = "contract_log"

    id = Column(CHAR(36), primary_key=True)
    log_object_id = Column(Integer, nullable=False)
    log_object_type = Column(Enum("contract", "worktype", "contract_type", "document_type"), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(CHAR(36), nullable=False, index=True)


class ContractParty(SupplyBase):
    __tablename__ = "contrarct_parties"

    id = Column(CHAR(36), primary_key=True)
    contract_id = Column(Integer, nullable=False, index=True)
    counterparties_id = Column(CHAR(36), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(CHAR(36), nullable=False, index=True)
    updated_by = Column(CHAR(36), nullable=True, index=True)
    updated_at = Column(DateTime, nullable=True)


class ContractUserRole(SupplyBase):
    __tablename__ = "contract_user_roles"

    id = Column(CHAR(36), primary_key=True)
    contract_id = Column(Integer, nullable=False, index=True)
    user_id = Column(CHAR(36), nullable=False, index=True)
    role = Column(Enum("creator", "executor", "co-executor", "observer"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(CHAR(36), nullable=False, index=True)


class WorkContract(SupplyBase):
    __tablename__ = "work_contract"

    id = Column(CHAR(36), primary_key=True)
    contract_work_type_id = Column(Integer, nullable=False, index=True)
    contract_id = Column(Integer, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(CHAR(36), nullable=False, index=True)


class ContractObject(SupplyBase):
    __tablename__ = "contract_object"

    id = Column(Integer, primary_key=True, autoincrement=True)
    object_id = Column(CHAR(36), nullable=False, index=True)
    object_type = Column(Enum("object", "object_levels_id"), nullable=False)
    contract_id = Column(Integer, nullable=False, index=True)


class ContractWorkTypeCreate(BaseModel):
    name: str


class ContractWorkTypeUpdate(BaseModel):
    name: str | None = Field(default=None)


class DocumentTypeCreate(BaseModel):
    name: str


class DocumentTypeUpdate(BaseModel):
    name: str | None = Field(default=None)


class ContractPartyCreate(BaseModel):
    contract_id: int
    counterparties_id: str
    name: str


class ContractPartyUpdate(BaseModel):
    contract_id: int | None = Field(default=None)
    counterparties_id: str | None = Field(default=None)
    name: str | None = Field(default=None)


class ContractUserRoleCreate(BaseModel):
    contract_id: int
    user_id: str
    role: Literal["creator", "executor", "co-executor", "observer"]


class ContractUserRoleUpdate(BaseModel):
    contract_id: int | None = Field(default=None)
    user_id: str | None = Field(default=None)
    role: Literal["creator", "executor", "co-executor", "observer"] | None = Field(default=None)


class WorkContractCreate(BaseModel):
    contract_id: int
    contract_work_type_id: int


class WorkContractUpdate(BaseModel):
    contract_id: int | None = Field(default=None)
    contract_work_type_id: int | None = Field(default=None)


class ContractObjectCreate(BaseModel):
    contract_id: int
    object_id: str
    object_type: Literal["object", "object_levels_id"]


class ContractObjectUpdate(BaseModel):
    contract_id: int | None = Field(default=None)
    object_id: str | None = Field(default=None)
    object_type: Literal["object", "object_levels_id"] | None = Field(default=None)


class ContractCreate(BaseModel):
    num: str | None = Field(default=None)
    internal_num: str | None = Field(default=None)
    date: dt_date | None = Field(default=None)
    document_type_id: str
    name: str | None = Field(default=None)
    date_start: dt_date | None = Field(default=None)
    date_end: dt_date | None = Field(default=None)
    date_completed: dt_date | None = Field(default=None)
    customer_id: str
    contractor_id: str
    type: Literal["provider", "buyer"] | None = Field(default=None)
    sum: float | None = Field(default=None)
    comment: str | None = Field(default=None)


class ContractUpdate(BaseModel):
    num: str | None = Field(default=None)
    internal_num: str | None = Field(default=None)
    date: dt_date | None = Field(default=None)
    document_type_id: str | None = Field(default=None)
    name: str | None = Field(default=None)
    date_start: dt_date | None = Field(default=None)
    date_end: dt_date | None = Field(default=None)
    date_completed: dt_date | None = Field(default=None)
    customer_id: str | None = Field(default=None)
    contractor_id: str | None = Field(default=None)
    type: Literal["provider", "buyer"] | None = Field(default=None)
    sum: float | None = Field(default=None)
    comment: str | None = Field(default=None)


class ContractFolderCreate(BaseModel):
    contract_id: int
    name: str
    parent_id: str | None = Field(default=None)


class ContractFolderUpdate(BaseModel):
    name: str | None = Field(default=None)
    parent_id: str | None = Field(default=None)


class ContractFileCreate(BaseModel):
    contract_id: int
    original_name: str
    storage_name: str
    extension: str | None = Field(default=None)
    file_path: str
    contract_folder_id: str | None = Field(default=None)
    type: str | None = Field(default=None)


class ContractFileUpdate(BaseModel):
    original_name: str | None = Field(default=None)
    extension: str | None = Field(default=None)
    contract_folder_id: str | None = Field(default=None)
    type: str | None = Field(default=None)
