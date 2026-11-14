from datetime import date, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import CHAR, Column, DateTime, Float, String, Text

# Which bank layout an uploaded Excel statement follows / which integration a fetched
# statement came from. Extend when a new bank's parser or API integration is added.
BANK_TYPES = ("sberbank", "alfabank", "tbank")

from app.database import SupplyBase


def msk_now():
    return datetime.utcnow() + timedelta(hours=3)


class ExtractItem(SupplyBase):
    __tablename__ = "extract_items"

    id = Column(String(36), primary_key=True)
    operationDate = Column(DateTime, nullable=True)
    amount = Column(Float(17, 8), nullable=True)
    direction = Column(Text, nullable=True)
    paymentPurpose = Column(Text, nullable=True)
    payeeInn = Column(Text, nullable=True)
    payeeKpp = Column(Text, nullable=True)
    payeeName = Column(Text, nullable=True)
    payerInn = Column(Text, nullable=True)
    payerKpp = Column(Text, nullable=True)
    payerName = Column(Text, nullable=True)
    payeeBankName = Column(Text, nullable=True)
    payeeAccount = Column(Text, nullable=True)
    account_number = Column(String(50), nullable=True, index=True)
    bank_type = Column(String(20), nullable=True, index=True)
    external_id = Column(String(100), nullable=True)
    payee_id = Column(CHAR(36), nullable=True, index=True)
    payer_id = Column(CHAR(36), nullable=True, index=True)
    object_id = Column(CHAR(36), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)


class ExtractItemUpdate(BaseModel):
    payee_id: str | None = Field(default=None)
    payer_id: str | None = Field(default=None)
    # reference_service.objects.id; pass null explicitly to detach the row from its object
    object_id: str | None = Field(default=None)


class ExtractItemSetObjectRequest(BaseModel):
    extract_ids: list[str] = Field(min_length=1, max_length=1000)
    object_id: str | None = Field(default=None, description="null — снять привязку к объекту")


class UploadExcelStatementRequest(BaseModel):
    bank_type: Literal["sberbank", "alfabank", "tbank"]
    account_number: str | None = Field(
        default=None,
        description="Если не передан, берётся номер счёта, найденный в самом файле выписки (не для всех банков есть в файле).",
    )


class FetchTbankStatementRequest(BaseModel):
    settings_api_bank_id: str
    account_number: str
    date_from: str = Field(description="ISO-8601, например 2026-09-23T21:00:00Z")
    date_to: str | None = Field(default=None, description="ISO-8601, опционально")


class FetchSberbankStatementRequest(BaseModel):
    settings_api_bank_id: str
    account_number: str
    # Either a single day...
    statement_date: str | None = Field(default=None)  # YYYY-MM-DD
    # ...or an inclusive range, processed day by day.
    statement_date_from: str | None = Field(default=None)  # YYYY-MM-DD
    statement_date_to: str | None = Field(default=None)  # YYYY-MM-DD

    @model_validator(mode="after")
    def _check_date_fields(self):
        has_single = bool(self.statement_date)
        has_range = bool(self.statement_date_from or self.statement_date_to)

        if has_single and has_range:
            raise ValueError("Укажите либо statement_date, либо statement_date_from/statement_date_to, не оба варианта")
        if not has_single and not has_range:
            raise ValueError("Укажите statement_date, либо statement_date_from и statement_date_to")

        if has_range:
            if not (self.statement_date_from and self.statement_date_to):
                raise ValueError("Для периода нужны оба поля: statement_date_from и statement_date_to")
            try:
                date_from = date.fromisoformat(self.statement_date_from)
                date_to = date.fromisoformat(self.statement_date_to)
            except ValueError as exc:
                raise ValueError("statement_date_from/statement_date_to должны быть в формате YYYY-MM-DD") from exc
            if date_from > date_to:
                raise ValueError("statement_date_from не может быть позже statement_date_to")

        return self

    def iter_dates(self) -> list[str]:
        if self.statement_date:
            return [self.statement_date]

        date_from = date.fromisoformat(self.statement_date_from)
        date_to = date.fromisoformat(self.statement_date_to)

        dates: list[str] = []
        current = date_from
        while current <= date_to:
            dates.append(current.isoformat())
            current += timedelta(days=1)
        return dates
