from datetime import datetime, timedelta

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import CHAR, Column, DateTime, String

from app.database import SupplyBase


def msk_now():
    return datetime.utcnow() + timedelta(hours=3)


class ReceiptSellerLogo(SupplyBase):
    __tablename__ = "receipt_seller_logos"

    id = Column(CHAR(36), primary_key=True)
    seller_inn = Column(String(12), nullable=False, unique=True)
    seller_name = Column(String(255), nullable=True)
    logo_url = Column(String(1000), nullable=True)
    storage_name = Column(String(100), nullable=True)
    mime_type = Column(String(100), nullable=True)
    created_by = Column(String(36), nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    updated_at = Column(DateTime, nullable=True)


class ReceiptSellerLogoSetUrl(BaseModel):
    logo_url: str = Field(min_length=8, max_length=1000, description="Ссылка на картинку, http(s)://...")
    seller_name: str | None = Field(default=None, max_length=255)

    @field_validator("logo_url")
    @classmethod
    def _http_only(cls, value: str) -> str:
        value = value.strip()
        if not value.lower().startswith(("http://", "https://")):
            raise ValueError("logo_url должен начинаться с http:// или https://")
        return value
