import uuid
from datetime import datetime, date as dt_date
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Column, DateTime, Enum, Integer, String, Text

from app.database import SupplyBase, msk_now


class DocumentsList(SupplyBase):
    __tablename__ = "documents_list"

    id = Column(Integer, primary_key=True, autoincrement=True)
    original_name = Column(Text, nullable=False)
    storage_name = Column(Text, nullable=False)
    extension = Column(String(100), nullable=False)
    file_path = Column(Text, nullable=False)
    uploaded_by = Column(CHAR(36), nullable=False, index=True)
    uploaded_at = Column(DateTime, nullable=False, default=msk_now)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(CHAR(36), nullable=True, index=True)
    type = Column(Enum("invoice", "upd", "contract", "act", "letter"), nullable=True)
    document_id = Column(String(36), nullable=True)
    document_type = Column(String(100), nullable=True)
    from_whom_id = Column(CHAR(36), nullable=True, index=True)
    object_id = Column(String(36), nullable=True)
    object_type = Column(Enum("object_id", "object_levels_id"), nullable=True)
    linked_file_id = Column(String(36), nullable=True, index=True)
    customer_id = Column(CHAR(36), nullable=True, index=True)
    contractor_id = Column(CHAR(36), nullable=True, index=True)


class DocumentsListCreate(BaseModel):
    type: Literal["invoice", "upd", "contract", "act", "letter"] | None = Field(default=None)
    document_id: str | None = Field(default=None)
    document_type: str | None = Field(default=None)
    from_whom_id: str | None = Field(default=None)
    object_id: str | None = Field(default=None)
    object_type: Literal["object_id", "object_levels_id"] | None = Field(default=None)
    customer_id: str | None = Field(default=None, description="Заказчик: id контрагента")
    contractor_id: str | None = Field(default=None, description="Подрядчик: id контрагента")


class DocumentsListUpdate(BaseModel):
    type: Literal["invoice", "upd", "contract", "act", "letter"] | None = Field(default=None)
    document_id: str | None = Field(default=None)
    document_type: str | None = Field(default=None)
    from_whom_id: str | None = Field(default=None)
    object_id: str | None = Field(default=None)
    object_type: Literal["object_id", "object_levels_id"] | None = Field(default=None)
    customer_id: str | None = Field(default=None, description="Заказчик: id контрагента; null - убрать")
    contractor_id: str | None = Field(default=None, description="Подрядчик: id контрагента; null - убрать")


class DocumentsListAttach(BaseModel):
    contract_id: int | None = Field(default=None)
    contract_folder_id: str | None = Field(default=None)
    act_id: int | None = Field(default=None)
    act_folder_id: str | None = Field(default=None)
    letter_id: int | None = Field(default=None)
    letter_folder_id: str | None = Field(default=None)
    type: str | None = Field(default=None)


class DocumentsListResponse(BaseModel):
    id: int
    original_name: str
    storage_name: str
    extension: str | None
    uploaded_by: str
    uploaded_at: datetime
    updated_at: datetime | None
    updated_by: str | None
    type: str | None
    document_id: str | None
    document_type: str | None
    from_whom_id: str | None
    object_id: str | None
    object_type: str | None
    customer_id: str | None = None
    contractor_id: str | None = None