from enum import Enum

from pydantic import BaseModel, Field
from sqlalchemy import Column, Enum as SqlEnum, Integer, String

from app.database import SupplyBase


class ObjectSettingsTemplateRoleType(str, Enum):
    VIEW_INVOICE = "view_invoice"
    CREATE_REQUEST = "create_request"
    APPROVE_REQUEST = "approve_request"


class ObjectSettingsTemplate(SupplyBase):
    __tablename__ = "object_settings_template"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=True, index=True)
    department_id = Column(Integer, nullable=True)
    role = Column(
        SqlEnum(ObjectSettingsTemplateRoleType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )


class ObjectSettingsTemplateCreate(BaseModel):
    id: str | None = Field(default=None)
    user_id: str | None = Field(default=None)
    department_id: int | None = Field(default=None)
    role: ObjectSettingsTemplateRoleType = Field(default=ObjectSettingsTemplateRoleType.VIEW_INVOICE)


class ObjectSettingsTemplateUpdate(BaseModel):
    user_id: str | None = Field(default=None)
    department_id: int | None = Field(default=None)
    role: ObjectSettingsTemplateRoleType | None = Field(default=None)
