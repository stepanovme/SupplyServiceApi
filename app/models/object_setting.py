from enum import Enum

from pydantic import BaseModel, Field
from sqlalchemy import Column, Enum as SqlEnum, Integer, String

from app.database import SupplyBase


class ObjectSettingsRoleType(str, Enum):
    VIEW_INVOICE = "view_invoice"
    CREATE_REQUEST = "create_request"
    APPROVE_REQUEST = "approve_request"


class ObjectSetting(SupplyBase):
    __tablename__ = "object_settings"

    id = Column(String(36), primary_key=True)
    object_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=True, index=True)
    department_id = Column(Integer, nullable=True)
    role = Column(
        SqlEnum(ObjectSettingsRoleType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )


class ObjectSettingCreate(BaseModel):
    id: str | None = Field(default=None)
    object_id: str = Field()
    user_id: str | None = Field(default=None)
    department_id: int | None = Field(default=None)
    role: ObjectSettingsRoleType = Field(default=ObjectSettingsRoleType.VIEW_INVOICE)


class ObjectSettingUpdate(BaseModel):
    user_id: str | None = Field(default=None)
    department_id: int | None = Field(default=None)
    role: ObjectSettingsRoleType | None = Field(default=None)
