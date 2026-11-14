from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Enum as SqlEnum, Integer, String

from app.database import SupplyBase, msk_now


class InvoiceUserRoleType(str, Enum):
    OBSERVER = "observer"


class InvoiceUser(SupplyBase):
    __tablename__ = "invoice_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(Integer, nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    role = Column(
        SqlEnum(InvoiceUserRoleType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(String(36), nullable=False)


class InvoiceUserCreate(BaseModel):
    invoice_id: int = Field()
    user_id: str = Field()
    role: InvoiceUserRoleType = Field(default=InvoiceUserRoleType.OBSERVER)


class InvoiceUserUpdate(BaseModel):
    role: InvoiceUserRoleType | None = Field(default=None)
