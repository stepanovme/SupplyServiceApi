from datetime import date as dt_date
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Column, Date, DateTime, Enum, Float, Integer, String, Text

from app.database import SupplyBase


def msk_now():
    return datetime.utcnow() + timedelta(hours=3)


class ObjectExpenditure(SupplyBase):
    __tablename__ = "object_expenditure"

    id = Column(Integer, primary_key=True, autoincrement=True)
    object_id = Column(String(36), nullable=False, index=True)
    type = Column(Enum("salary", "work", "tax", "other"), nullable=False)
    sum = Column(Float(17, 8), nullable=False)
    date = Column(Date, nullable=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)
    comment = Column(Text, nullable=True)


class ObjectExpenditureCreate(BaseModel):
    object_id: str
    type: Literal["salary", "work", "tax", "other"]
    sum: float
    date: dt_date | None = Field(default=None)
    comment: str | None = Field(default=None)


class ObjectExpenditureUpdate(BaseModel):
    type: Literal["salary", "work", "tax", "other"] | None = Field(default=None)
    sum: float | None = Field(default=None)
    date: dt_date | None = Field(default=None)
    comment: str | None = Field(default=None)
