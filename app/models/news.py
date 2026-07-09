from __future__ import annotations
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import JSON, CHAR, Column, DateTime, Integer, Text, Boolean

from app.database import SupplyBase, msk_now


class NewsPost(SupplyBase):
    __tablename__ = "news_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(Text, nullable=True)
    slug = Column(Text, nullable=True)
    cover = Column(Text, nullable=True)
    excerpt = Column(Text, nullable=True)
    content = Column(JSON, nullable=False)
    is_published = Column(Boolean, nullable=False, default=False)
    published_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(CHAR(36), nullable=True)


class NewsPostCreate(BaseModel):
    title: str | None = None
    cover: str | None = None
    content: Any
    is_published: bool = False
    published_at: datetime | None = None


class NewsPostUpdate(BaseModel):
    title: str | None = None
    cover: str | None = None
    excerpt: str | None = None
    content: Any | None = None
    is_published: bool | None = None
    published_at: datetime | None = None
