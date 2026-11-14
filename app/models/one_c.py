from app.database import msk_now
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import CHAR, Column, DateTime, ForeignKey, Integer, String, Text

from app.database import SupplyBase


class OneCProfile(SupplyBase):
    __tablename__ = "1c_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(300), nullable=False)
    username = Column(String(100), nullable=False)
    password = Column(Text, nullable=False)
    api_link = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=True, default=msk_now)
    created_by = Column(CHAR(36), nullable=True, index=True)
    updated_at = Column(DateTime, nullable=True, default=msk_now)
    updated_by = Column(CHAR(36), nullable=True, index=True)


class OneCOrganization(SupplyBase):
    __tablename__ = "1с_organizations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ref_key = Column(CHAR(36), nullable=False)
    name = Column(Text, nullable=False)
    inn = Column(String(100), nullable=False)
    one_c_profile_id = Column("1c_profile_id", Integer, ForeignKey("1c_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=True, default=msk_now)
    created_by = Column(CHAR(36), nullable=True, index=True)


class OneCProfileCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    username: str
    password: str
    api_link: str


class OneCProfileUpdate(BaseModel):
    name: str | None = Field(default=None)
    username: str | None = Field(default=None)
    password: str | None = Field(default=None)
    api_link: str | None = Field(default=None)


class OneCOrganizationCreate(BaseModel):
    ref_key: str
    name: str
    inn: str
    one_c_profile_id: int


class OneCOrganizationUpdate(BaseModel):
    ref_key: str | None = Field(default=None)
    name: str | None = Field(default=None)
    inn: str | None = Field(default=None)
    one_c_profile_id: int | None = Field(default=None)


class OneCSyncRequest(BaseModel):
    profile_ids: list[int] | None = Field(default=None)
    organization_ref_keys: list[str] | None = Field(default=None)
    date_from: datetime | None = Field(default=None)
    date_to: datetime | None = Field(default=None)
