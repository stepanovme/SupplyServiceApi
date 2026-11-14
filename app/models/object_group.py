from datetime import datetime, timedelta

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Column, DateTime, ForeignKey, Integer, String, Text

from app.database import ReferenceBase


def msk_now():
    return datetime.utcnow() + timedelta(hours=3)


class ObjectGroup(ReferenceBase):
    __tablename__ = "object_groups"

    id = Column(CHAR(36), primary_key=True)
    name = Column(String(255), nullable=False)
    main_object_id = Column(CHAR(36), nullable=False, unique=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    updated_at = Column(DateTime, nullable=True)
    created_by = Column(CHAR(36), nullable=False, index=True)


class ObjectGroupMember(ReferenceBase):
    __tablename__ = "object_group_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(CHAR(36), ForeignKey("object_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    object_id = Column(CHAR(36), nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False)


class ObjectGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    main_object_id: str
    object_ids: list[str] = Field(default_factory=list)
    comment: str | None = None


class ObjectGroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    main_object_id: str | None = None
    comment: str | None = None


class ObjectGroupAddObjects(BaseModel):
    object_ids: list[str] = Field(min_length=1)
