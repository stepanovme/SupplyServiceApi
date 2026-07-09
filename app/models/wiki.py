from __future__ import annotations
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import JSON, CHAR, Boolean, Column, DateTime, Enum, Integer, Text, VARCHAR

from app.database import SupplyBase, msk_now


class WikiPage(SupplyBase):
    __tablename__ = "wiki_pages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(Text, nullable=False)
    slug = Column(VARCHAR(255), nullable=False)
    parent_id = Column(Integer, nullable=True)
    kind = Column(Enum("section", "page"), nullable=False)
    content = Column(JSON, nullable=False)
    position = Column(Integer, nullable=False)
    is_published = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(CHAR(36), nullable=True)


class WikiPageCreate(BaseModel):
    title: str
    parent_id: int | None = None
    kind: Literal["section", "page"]


class WikiPageUpdate(BaseModel):
    title: str | None = None
    content: Any | None = None
    parent_id: int | None = None
    position: int | None = None
    is_published: bool | None = None
