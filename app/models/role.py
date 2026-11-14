import uuid
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import JSON, Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import SupplyBase, msk_now


def msk_now():
    return datetime.utcnow() + timedelta(hours=3)


class Role(SupplyBase):
    __tablename__ = "roles"

    id = Column(String(36), primary_key=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(String(36), nullable=False, index=True)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(String(36), nullable=True)


class RolePermission(SupplyBase):
    __tablename__ = "role_permissions"

    id = Column(String(36), primary_key=True)
    role_id = Column(String(36), nullable=False, index=True)
    permission_key = Column(Enum("requests", "objects", name="rp_permission_key"), nullable=False, index=True)
    settings = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(String(36), nullable=False, index=True)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(String(36), nullable=True)


class UserRole(SupplyBase):
    __tablename__ = "user_roles"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    role_id = Column(String(36), nullable=False, index=True)
    assigned_by = Column(String(36), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)


class DepartmentRole(SupplyBase):
    __tablename__ = "department_roles"

    id = Column(String(36), primary_key=True)
    department_id = Column(Integer, nullable=False, index=True)
    role_id = Column(String(36), nullable=False, index=True)
    assigned_by = Column(String(36), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)


# ── Pydantic schemas ──────────────────────────────────────────────────

class RoleCreate(BaseModel):
    name: str
    description: str | None = None


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class RolePermissionCreate(BaseModel):
    permission_key: Literal["requests", "objects"]
    settings: dict | None = None


class RolePermissionUpdate(BaseModel):
    settings: dict | None = None


class AssignUserRole(BaseModel):
    role_id: str


class AssignDepartmentRole(BaseModel):
    role_id: str
