from datetime import date, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Column, Date, DateTime, Enum, FetchedValue, ForeignKey, Integer, Numeric, String, Text

from app.database import SupplyBase


def msk_now():
    return datetime.utcnow() + timedelta(hours=3)


class AdvanceReport(SupplyBase):
    __tablename__ = "advance_reports"

    id = Column(CHAR(36), primary_key=True)
    number = Column(Integer, server_default=FetchedValue(), unique=True)  # AUTO_INCREMENT in the database
    title = Column(String(255), nullable=True)
    report_date = Column(Date, nullable=False)
    comment = Column(Text, nullable=True)
    person_user_id = Column(String(36), nullable=True)
    status = Column(Enum("draft", "sent"), nullable=False, default="draft")
    total_sum = Column(Numeric(14, 2), nullable=False, default=0)
    one_c_profile_id = Column(Integer, nullable=True)
    one_c_organization_ref_key = Column(CHAR(36), nullable=True)
    one_c_organization_name = Column(String(300), nullable=True)
    one_c_person_ref_key = Column(CHAR(36), nullable=True)
    one_c_person_name = Column(String(300), nullable=True)
    one_c_ref_key = Column(CHAR(36), nullable=True)
    one_c_number = Column(String(50), nullable=True)
    one_c_sent_at = Column(DateTime, nullable=True)
    one_c_sent_by = Column(String(36), nullable=True)
    one_c_error = Column(Text, nullable=True)
    created_by = Column(String(36), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    updated_at = Column(DateTime, nullable=True)


class AdvanceReportReceipt(SupplyBase):
    __tablename__ = "advance_report_receipts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(CHAR(36), ForeignKey("advance_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    receipt_id = Column(CHAR(36), nullable=False, unique=True)
    added_by = Column(String(36), nullable=False)
    added_at = Column(DateTime, nullable=False, default=msk_now)


class OneCSendOptions(BaseModel):
    """Where and how the report goes to 1C."""

    profile_id: int = Field(description="Профиль 1С (GET /advance-reports/1c/profiles)")
    organization_ref_key: str | None = Field(
        default=None, description="Организация в 1С (Ref_Key); можно не указывать, если в базе одна организация"
    )
    person_ref_key: str | None = Field(
        default=None, description="Подотчётное лицо в 1С (Ref_Key физического лица); в тестовой базе без физлиц создаётся тестовое"
    )
    nomenclature_mode: Literal["match", "create", "generic"] | None = Field(
        default=None,
        description=(
            "Как подбирать номенклатуру: match - только найти по точному названию (нет совпадения - ошибка со списком), "
            "create - найти или создать (только в тестовых профилях), generic - одна общая номенклатура "
            "generic_nomenclature_ref_key для всех строк. По умолчанию: create для тестового профиля, иначе match"
        ),
    )
    generic_nomenclature_ref_key: str | None = Field(default=None, description="Ref_Key общей номенклатуры для режима generic")


class AdvanceReportCreate(BaseModel):
    receipt_ids: list[str] = Field(min_length=1, max_length=200)
    title: str | None = Field(default=None, max_length=255)
    report_date: date | None = Field(default=None, description="Дата отчёта; по умолчанию сегодня")
    comment: str | None = Field(default=None)
    person_user_id: str | None = Field(default=None, description="Подотчётное лицо у нас (пользователь), необязательно")
    one_c: OneCSendOptions | None = Field(default=None, description="Если указано — отчёт сразу отправляется в 1С через этот профиль")


class AdvanceReportUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    report_date: date | None = Field(default=None)
    comment: str | None = Field(default=None)
    person_user_id: str | None = Field(default=None, description="null - убрать")


class AdvanceReportReceiptsAdd(BaseModel):
    receipt_ids: list[str] = Field(min_length=1, max_length=200)
