from datetime import date as dt_date
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import CHAR, Boolean, Column, Date, DateTime, Enum, String

from app.database import SupplyBase


def msk_now():
    return datetime.utcnow() + timedelta(hours=3)


# Which real-world bank issued the card. Kept separate from `source` (manual vs
# synced from an API) - a manually entered card still needs to say which bank it's
# from, and this list is independent of which banks have a settings_api_bank
# integration set up (currently only sberbank does).
BANK_TYPES = ("sberbank", "alfabank", "tbank")


class BusinessCard(SupplyBase):
    __tablename__ = "business_cards"

    id = Column(CHAR(36), primary_key=True)
    settings_api_bank_id = Column(CHAR(36), nullable=True, index=True)
    bank_business_card_id = Column(String(64), nullable=True)
    source = Column(Enum("manual", "sberbank"), nullable=False, default="manual")
    bank_type = Column(Enum(*BANK_TYPES), nullable=True)
    account_number = Column(String(50), nullable=True)
    card_number_mask = Column(String(32), nullable=True)
    card_last4 = Column(String(4), nullable=True, index=True)
    embossed_name = Column(String(255), nullable=True)
    holder_name = Column(String(255), nullable=True)
    holder_user_id = Column(CHAR(36), nullable=True, index=True)
    card_open_date = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True)
    card_status = Column(String(20), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    updated_at = Column(DateTime, nullable=True)
    created_by = Column(CHAR(36), nullable=False, index=True)


class BusinessCardCreate(BaseModel):
    card_number_mask: str
    bank_type: Literal["sberbank", "alfabank", "tbank"]
    holder_name: str | None = Field(default=None)
    holder_user_id: str | None = Field(default=None)
    account_number: str | None = Field(default=None)
    embossed_name: str | None = Field(default=None)
    card_open_date: dt_date | None = Field(default=None)
    expiry_date: dt_date | None = Field(default=None)
    card_status: str | None = Field(default=None)
    is_active: bool = Field(default=True)


class BusinessCardUpdate(BaseModel):
    card_number_mask: str | None = Field(default=None)
    bank_type: Literal["sberbank", "alfabank", "tbank"] | None = Field(default=None)
    holder_name: str | None = Field(default=None)
    holder_user_id: str | None = Field(default=None)
    account_number: str | None = Field(default=None)
    embossed_name: str | None = Field(default=None)
    card_open_date: dt_date | None = Field(default=None)
    expiry_date: dt_date | None = Field(default=None)
    card_status: str | None = Field(default=None)
    is_active: bool | None = Field(default=None)


class FetchSberbankCardsRequest(BaseModel):
    settings_api_bank_id: str


class ExtractBusinessCard(SupplyBase):
    __tablename__ = "extract_business_cards"

    id = Column(CHAR(36), primary_key=True)
    extract_id = Column(String(36), nullable=False, index=True)
    business_card_id = Column(CHAR(36), nullable=False, index=True)
    object_id = Column(CHAR(36), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)


class ExtractBusinessCardCreate(BaseModel):
    extract_id: str
    business_card_id: str
    object_id: str | None = Field(default=None)


class ExtractBusinessCardUpdate(BaseModel):
    business_card_id: str | None = Field(default=None)
    object_id: str | None = Field(default=None)
    clear_object: bool = Field(default=False)


class ExtractBusinessCardMatchAllRequest(BaseModel):
    extract_ids: list[str] | None = Field(default=None)
    date_from: datetime | None = Field(default=None)
    date_to: datetime | None = Field(default=None)
    limit: int = Field(default=50, ge=1, le=1000)

    @model_validator(mode="after")
    def _check(self):
        if self.extract_ids is not None and len(self.extract_ids) == 0:
            raise ValueError("extract_ids не может быть пустым списком")
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from не может быть позже date_to")
        return self
