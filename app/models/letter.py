import time
import uuid
from datetime import date as date_type, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Column, Date, DateTime, Enum, Float, Integer, String, Text

from app.database import SupplyBase


def msk_now():
    return datetime.utcnow() + timedelta(hours=3)


class Letter(SupplyBase):
    __tablename__ = "letter"

    id = Column(Integer, primary_key=True, autoincrement=True)
    internal_num = Column(String(30), nullable=False)
    num = Column(String(100), nullable=True)
    name = Column(Text, nullable=True)
    from_to = Column(CHAR(36), nullable=False, index=True)
    where_to = Column(CHAR(36), nullable=False, index=True)
    type = Column(Enum("outgoing", "incoming"), nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)


class LetterFolder(SupplyBase):
    __tablename__ = "letter_folders"

    id = Column(CHAR(36), primary_key=True)
    letter_id = Column(Integer, nullable=False, index=True)
    name = Column(Text, nullable=False)
    parent_id = Column(CHAR(36), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(CHAR(36), nullable=True, index=True)


class LetterFile(SupplyBase):
    __tablename__ = "letter_files"

    id = Column(CHAR(36), primary_key=True)
    letter_id = Column(Integer, nullable=False, index=True)
    original_name = Column(Text, nullable=False)
    storage_name = Column(Text, nullable=False)
    extension = Column(String(100), nullable=True)
    file_path = Column(Text, nullable=False)
    type = Column(Enum("original", "version"), nullable=True)
    uploaded_by = Column(CHAR(36), nullable=False, index=True)
    uploaded_at = Column(DateTime, nullable=False, default=msk_now)
    letter_folder_id = Column(CHAR(36), nullable=True, index=True)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(CHAR(36), nullable=True, index=True)


class LetterObject(SupplyBase):
    __tablename__ = "letter_objects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    letter_id = Column(Integer, nullable=False, index=True)
    object_id = Column(CHAR(36), nullable=False)
    object_type = Column(Enum("object", "object_levels_id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)


class LetterStatus(SupplyBase):
    __tablename__ = "letter_status"

    id = Column(Integer, primary_key=True, autoincrement=True)
    letter_id = Column(Integer, nullable=False, index=True)
    type_movement = Column(Enum("departure", "receiving"), nullable=True)
    date = Column(Date, nullable=False)
    type = Column(Enum("mail_russia", "mail", "edo", "director", "accountant", "lawyer", "signed", "prepared"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)


class LetterUserRole(SupplyBase):
    __tablename__ = "letter_user_roles"

    id = Column(CHAR(36), primary_key=True)
    letter_id = Column(Integer, nullable=False, index=True)
    user_id = Column(CHAR(36), nullable=False, index=True)
    role = Column(Enum("creator", "executor", "co-executor", "observer"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)


# --- Pydantic schemas ---

class LetterCreate(BaseModel):
    internal_num: str | None = Field(default=None)
    num: str | None = Field(default=None)
    name: str | None = Field(default=None)
    from_to: str
    where_to: str
    type: Literal["outgoing", "incoming"]
    comment: str | None = Field(default=None)


class LetterUpdate(BaseModel):
    internal_num: str | None = Field(default=None)
    num: str | None = Field(default=None)
    name: str | None = Field(default=None)
    from_to: str | None = Field(default=None)
    where_to: str | None = Field(default=None)
    type: Literal["outgoing", "incoming"] | None = Field(default=None)
    comment: str | None = Field(default=None)


class LetterFolderCreate(BaseModel):
    letter_id: int
    name: str
    parent_id: str | None = Field(default=None)


class LetterFolderUpdate(BaseModel):
    name: str | None = Field(default=None)
    parent_id: str | None = Field(default=None)


class LetterFileCreate(BaseModel):
    letter_id: int
    original_name: str
    storage_name: str
    extension: str | None = Field(default=None)
    file_path: str
    letter_folder_id: str | None = Field(default=None)
    type: str | None = Field(default=None)


class LetterFileUpdate(BaseModel):
    original_name: str | None = Field(default=None)
    extension: str | None = Field(default=None)
    letter_folder_id: str | None = Field(default=None)
    type: str | None = Field(default=None)


class LetterObjectCreate(BaseModel):
    letter_id: int
    object_id: str
    object_type: Literal["object", "object_levels_id"]


class LetterObjectUpdate(BaseModel):
    letter_id: int | None = Field(default=None)
    object_id: str | None = Field(default=None)
    object_type: Literal["object", "object_levels_id"] | None = Field(default=None)


class LetterStatusCreate(BaseModel):
    letter_id: int
    type_movement: Literal["departure", "receiving"] | None = Field(default=None)
    date: date_type
    type: Literal["mail_russia", "mail", "edo", "director", "accountant", "lawyer", "signed", "prepared"]


class LetterStatusUpdate(BaseModel):
    type_movement: Literal["departure", "receiving"] | None = Field(default=None)
    date: date_type | None = Field(default=None)
    type: Literal["mail_russia", "mail", "edo", "director", "accountant", "lawyer", "signed", "prepared"] | None = Field(default=None)


class LetterUserRoleCreate(BaseModel):
    letter_id: int
    user_id: str
    role: Literal["creator", "executor", "co-executor", "observer"]


class LetterUserRoleUpdate(BaseModel):
    user_id: str | None = Field(default=None)
    role: Literal["creator", "executor", "co-executor", "observer"] | None = Field(default=None)
