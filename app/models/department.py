from __future__ import annotations
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import CHAR, Column, DateTime, Enum, Integer, Text

from app.database import SupplyBase, msk_now


class Department(SupplyBase):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(CHAR(36), nullable=True)


class DepartmentCreate(BaseModel):
    name: str


class DepartmentUpdate(BaseModel):
    name: str | None = None


class DepartmentUser(SupplyBase):
    __tablename__ = "department_users"

    id = Column(CHAR(36), primary_key=True)
    departament_id = Column(Integer, nullable=False)
    user_id = Column(CHAR(36), nullable=False)
    role_id = Column(Enum("admin", "participant", "creator"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False)


class DepartmentUserCreate(BaseModel):
    departament_id: int
    user_id: str
    role_id: Literal["admin", "participant", "creator"]


class DepartmentUserUpdate(BaseModel):
    role_id: Literal["admin", "participant", "creator"] | None = None
