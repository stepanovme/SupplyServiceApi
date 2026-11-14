from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Boolean, Column, DateTime, JSON, String, ForeignKey

from app.database import SupplyBase


def msk_now():
    return datetime.utcnow() + timedelta(hours=3)


# Extend this tuple (and the pydantic Literal below) when adding a new bank type.
BANK_TYPES = ("sberbank", "tbank")

# Config keys accepted per bank_type. "pfx_path" is filled by the server (file upload
# endpoint), never accepted directly from the client in create/update payloads.
BANK_CONFIG_FIELDS: dict[str, dict[str, bool]] = {
    # field_name -> required
    "sberbank": {
        "api_host": True,
        "api_token": True,
        "pfx_passphrase": False,
        # Optional TLS overrides for hosts whose certificate chain isn't trusted
        # by the system store out of the box (e.g. a sandbox with a self-signed root).
        "ca_bundle_path": False,
        "ssl_verify": False,
    },
    # T-Bank (Tinkoff Business OpenAPI): Bearer token + a client TLS certificate (mTLS) -
    # a plain cert/key PEM pair (not a PFX bundle like Sberbank). "cert_path"/"key_path"
    # are filled by the server (file upload endpoint), never accepted directly from the
    # client in create/update payloads. api_host defaults to https://business.tbank.ru.
    "tbank": {
        "api_host": False,
        "api_token": True,
        "ca_bundle_path": False,
        "ssl_verify": False,
    },
}

DEFAULT_TBANK_API_HOST = "https://business.tbank.ru"

# Config keys that must never be returned as-is in API responses.
SECRET_CONFIG_FIELDS = {"api_token", "pfx_passphrase"}


class SettingsApiBank(SupplyBase):
    __tablename__ = "settings_api_bank"

    id = Column(CHAR(36), primary_key=True)
    name = Column(String(255), nullable=False)
    bank_type = Column(String(50), nullable=False, index=True)
    config = Column(JSON, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    updated_at = Column(DateTime, nullable=True)
    created_by = Column(CHAR(36), nullable=False, index=True)
    updated_by = Column(CHAR(36), nullable=True)


class SettingsApiBankCreate(BaseModel):
    name: str
    bank_type: Literal["sberbank", "tbank"]
    config: dict = Field(default_factory=dict)
    is_active: bool = Field(default=True)


class SettingsApiBankUpdate(BaseModel):
    name: str | None = Field(default=None)
    config: dict | None = Field(default=None)
    is_active: bool | None = Field(default=None)


class SettingsApiBankAccount(SupplyBase):
    __tablename__ = "settings_api_bank_accounts"

    id = Column(CHAR(36), primary_key=True)
    settings_api_bank_id = Column(
        CHAR(36), ForeignKey("settings_api_bank.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_number = Column(String(50), nullable=False)
    name = Column(String(255), nullable=True)
    currency = Column(String(10), nullable=False, default="RUB")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    updated_at = Column(DateTime, nullable=True)
    created_by = Column(CHAR(36), nullable=False, index=True)
    updated_by = Column(CHAR(36), nullable=True)


class SettingsApiBankAccountCreate(BaseModel):
    account_number: str
    name: str | None = Field(default=None)
    currency: str = Field(default="RUB")
    is_active: bool = Field(default=True)


class SettingsApiBankAccountUpdate(BaseModel):
    account_number: str | None = Field(default=None)
    name: str | None = Field(default=None)
    currency: str | None = Field(default=None)
    is_active: bool | None = Field(default=None)
