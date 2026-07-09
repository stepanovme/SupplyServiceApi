from __future__ import annotations
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import CHAR, Column, DateTime, String

from app.database import SupplyBase, msk_now


class DocumentsLink(SupplyBase):
    __tablename__ = "documents_links"

    id = Column(CHAR(36), primary_key=True)
    document_linked_first = Column(String(36), nullable=False)
    document_type_first = Column(String(100), nullable=False)
    document_linked_second = Column(String(36), nullable=False)
    document_type_second = Column(String(100), nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False)


class DocumentsLinkCreate(BaseModel):
    document_linked_first: str
    document_type_first: str
    document_linked_second: str
    document_type_second: str


class DocumentsLinkUpdate(BaseModel):
    document_linked_first: str | None = None
    document_type_first: str | None = None
    document_linked_second: str | None = None
    document_type_second: str | None = None


class DocumentsLinkResponse(BaseModel):
    id: str
    document_linked_first: str
    document_type_first: str
    document_linked_second: str
    document_type_second: str
    created_at: datetime
    created_by: str
