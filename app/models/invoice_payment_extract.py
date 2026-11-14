from datetime import datetime, timedelta

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import CHAR, Column, DateTime, Float, String, UniqueConstraint

from app.database import SupplyBase


def msk_now():
    return datetime.utcnow() + timedelta(hours=3)


class InvoicePaymentExtract(SupplyBase):
    __tablename__ = "invoice_payment_extracts"
    # One statement row may be spread over several invoice payments (and one payment may be
    # backed by several rows); only the exact same pair can't be linked twice.
    __table_args__ = (UniqueConstraint("extract_id", "invoice_payment_id", name="uq_invoice_payment_extracts_pair"),)

    id = Column(CHAR(36), primary_key=True)
    invoice_payment_id = Column(String(36), nullable=False, index=True)
    extract_id = Column(String(36), nullable=False, index=True)
    # exact | bumped | split | created (set by the auto-matcher) | manual
    scenario = Column(String(20), nullable=False)
    amount = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(String(36), nullable=False, index=True)


class InvoicePaymentExtractCreate(BaseModel):
    extract_id: str
    invoice_payment_id: str
    amount: float | None = Field(
        default=None,
        gt=0,
        description="Часть суммы строки выписки, относящаяся к этому платежу. "
        "Не указана — берётся ещё не распределённый остаток строки выписки.",
    )


class InvoicePaymentExtractLinkItem(BaseModel):
    invoice_payment_id: str
    amount: float = Field(gt=0)


class InvoicePaymentExtractBulkCreate(BaseModel):
    """Attach one statement row to several invoice payments in one atomic call."""

    extract_id: str
    links: list[InvoicePaymentExtractLinkItem] = Field(min_length=1)

    @model_validator(mode="after")
    def _no_duplicate_payments(self):
        ids = [l.invoice_payment_id for l in self.links]
        if len(ids) != len(set(ids)):
            raise ValueError("Один и тот же invoice_payment_id указан в links несколько раз")
        return self


class InvoicePaymentExtractUpdate(BaseModel):
    amount: float = Field(gt=0)


class InvoicePaymentExtractMatchAllRequest(BaseModel):
    # Explicit set of extract_items to process - takes priority over date_from/date_to/limit.
    extract_ids: list[str] | None = Field(default=None)
    date_from: datetime | None = Field(default=None)
    date_to: datetime | None = Field(default=None)
    limit: int = Field(default=50, ge=1, le=1000)
    dry_run: bool = Field(
        default=False,
        description="Только показать, что будет сделано с платежами, ничего не записывая в БД.",
    )
    use_ai: bool = Field(
        default=True,
        description="Если регулярка не нашла номер/дату счёта, попробовать найти их через ИИ.",
    )

    @model_validator(mode="after")
    def _check(self):
        if self.extract_ids is not None and len(self.extract_ids) == 0:
            raise ValueError("extract_ids не может быть пустым списком")
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from не может быть позже date_to")
        return self
