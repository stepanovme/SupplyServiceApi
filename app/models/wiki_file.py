from __future__ import annotations
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import CHAR, Column, DateTime, Integer, Text

from app.database import SupplyBase, msk_now


class WikiFile(SupplyBase):
    __tablename__ = "wiki_files"

    id = Column(CHAR(36), primary_key=True)
    filename = Column(Text, nullable=False)
    path = Column(Text, nullable=False)
    url = Column(Text, nullable=False)
    mime = Column(Text, nullable=False)
    size = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False)


class WikiFileResponse(BaseModel):
    id: str
    filename: str
    path: str
    url: str
    mime: str
    size: int
    created_at: datetime
    created_by: str
