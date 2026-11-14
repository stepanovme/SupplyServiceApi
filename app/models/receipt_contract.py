from datetime import date as dt_date
from datetime import datetime, timedelta

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Column, Date, DateTime, Float, Integer, Text

from app.database import SupplyBase


def msk_now():
    return datetime.utcnow() + timedelta(hours=3)


class ReceiptContract(SupplyBase):
    __tablename__ = "receipt_contract"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(Integer, nullable=False, index=True)
    sum = Column(Float(17, 8), nullable=False)
    date = Column(Date, nullable=True)
    created_by = Column(CHAR(36), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    comment = Column(Text, nullable=True)


class ReceiptContractCreate(BaseModel):
    contract_id: int
    sum: float
    date: dt_date | None = Field(default=None)
    comment: str | None = Field(default=None)


class ReceiptContractUpdate(BaseModel):
    sum: float | None = Field(default=None)
    date: dt_date | None = Field(default=None)
    comment: str | None = Field(default=None)
