from datetime import date as dt_date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Column, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text

from app.database import SupplyBase, msk_now
from app.models.object_ref import ObjectRef

ESTIMATE_STATUSES = {"draft": "Черновик", "planning": "Планирование", "in_progress": "В работе", "completed": "Завершено"}
ESTIMATE_KINDS = {"main": "Основная", "contractor": "Подрядчика"}
APPROVAL_STATUSES = {"pending": "Не утверждена", "approved": "Утверждена"}
RESOURCE_TYPES = {"material": "Материалы", "machine": "Механизмы", "overhead": "Накладные", "labor": "Люди", "profit": "Сметная прибыль"}

EstimateKind = Literal["main", "contractor"]
EstimateStatus = Literal["draft", "planning", "in_progress", "completed"]
ResourceType = Literal["material", "machine", "overhead", "labor", "profit"]


class Estimate(SupplyBase):
    __tablename__ = "estimates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    status = Column(Enum(*ESTIMATE_STATUSES, name="estimate_status"), nullable=False, default="draft")
    object_id = Column(CHAR(36), nullable=True, index=True)
    object_type = Column(Enum("object", "object_levels_id", name="estimate_object_type"), nullable=True)
    comment = Column(Text, nullable=True)
    customer_id = Column(CHAR(36), nullable=True)
    investor_id = Column(CHAR(36), nullable=True)
    contractor_id = Column(CHAR(36), nullable=True)
    kind = Column(Enum(*ESTIMATE_KINDS, name="estimate_kind"), nullable=False, default="main")
    executor_id = Column(CHAR(36), nullable=True)
    contract_id = Column(Integer, nullable=True)
    approval_status = Column(Enum(*APPROVAL_STATUSES, name="estimate_approval_status"), nullable=False, default="pending")
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(CHAR(36), nullable=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(CHAR(36), nullable=True)


class EstimateSection(SupplyBase):
    __tablename__ = "estimate_sections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    estimate_id = Column(Integer, ForeignKey("estimates.id", ondelete="CASCADE"), nullable=False, index=True)
    position = Column(Integer, nullable=False)
    name = Column(String(255), nullable=False)


class EstimateWork(SupplyBase):
    __tablename__ = "estimate_works"

    id = Column(Integer, primary_key=True, autoincrement=True)
    section_id = Column(Integer, ForeignKey("estimate_sections.id", ondelete="CASCADE"), nullable=False, index=True)
    position = Column(Integer, nullable=False)
    name = Column(String(255), nullable=False)
    unit_name = Column(String(50), nullable=True)
    quantity = Column(Numeric(18, 4), nullable=False, default=0)


class EstimateWorkPeriod(SupplyBase):
    __tablename__ = "estimate_work_periods"

    id = Column(Integer, primary_key=True, autoincrement=True)
    work_id = Column(Integer, ForeignKey("estimate_works.id", ondelete="CASCADE"), nullable=False, index=True)
    date_from = Column(Date, nullable=False)
    date_to = Column(Date, nullable=False)


class EstimateWorkProgress(SupplyBase):
    """Факт выполнения работы: сколько сделано в какой день."""
    __tablename__ = "estimate_work_progress"

    id = Column(Integer, primary_key=True, autoincrement=True)
    work_id = Column(Integer, ForeignKey("estimate_works.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    quantity = Column(Numeric(18, 4), nullable=False)
    contractor_id = Column(CHAR(36), nullable=True, index=True)
    comment = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(CHAR(36), nullable=True)


class EstimateResource(SupplyBase):
    __tablename__ = "estimate_resources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    work_id = Column(Integer, ForeignKey("estimate_works.id", ondelete="CASCADE"), nullable=False, index=True)
    position = Column(Integer, nullable=False)
    type = Column(Enum(*RESOURCE_TYPES, name="estimate_resource_type"), nullable=False)
    name = Column(String(255), nullable=False)
    contractor_id = Column(CHAR(36), nullable=True, index=True)
    quantity = Column(Numeric(18, 4), nullable=False, default=0)
    unit_name = Column(String(50), nullable=True)
    unit_price = Column(Numeric(18, 2), nullable=False, default=0)
    markup_percent = Column(Numeric(9, 2), nullable=False, default=0)


# --- schemas ---
class EstimateCreate(BaseModel):
    kind: EstimateKind = Field(default="main", description="main - основная смета, contractor - смета подрядчика (независимая)")
    executor_id: str | None = Field(default=None, description="Подрядчик-исполнитель (обязателен для kind=contractor)")
    contract_id: int | None = Field(default=None, description="Договор из реестра договоров (только для сметы подрядчика)")
    name: str = Field(min_length=1, max_length=255)
    status: EstimateStatus = "draft"
    object: ObjectRef | None = Field(default=None, description="Объект сметы")
    comment: str | None = None
    customer_id: str | None = Field(default=None, description="Заказчик (контрагент)")
    investor_id: str | None = Field(default=None, description="Инвестор (контрагент)")
    contractor_id: str | None = Field(default=None, description="Подрядчик по смете - заказчик для наших подрядчиков (контрагент)")


class EstimateUpdate(BaseModel):
    executor_id: str | None = Field(default=None, description="Подрядчик-исполнитель сметы подрядчика (у утверждённой менять нельзя)")
    contract_id: int | None = Field(default=None, description="Договор из реестра; null - открепить")
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: EstimateStatus | None = None
    object: ObjectRef | None = Field(default=None, description="null - отвязать от объекта")
    comment: str | None = None
    customer_id: str | None = Field(default=None, description="Заказчик (контрагент); null - убрать")
    investor_id: str | None = Field(default=None, description="Инвестор (контрагент); null - убрать")
    contractor_id: str | None = Field(default=None, description="Подрядчик по смете - заказчик для наших подрядчиков (контрагент)")


class SectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    position: int | None = Field(default=None, ge=1, description="Куда вставить (по умолчанию - в конец)")


class SectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    position: int | None = Field(default=None, ge=1)


class WorkCreate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255, description="Обязательно, если не задан price_item_id")
    price_item_id: int | None = Field(default=None, description="Позиция справочника работ: название, единица, количество и состав (ресурсы) берутся из неё; явно переданные поля важнее")
    unit_name: str | None = Field(default=None, max_length=50)
    quantity: Decimal | None = Field(default=None, ge=0, description="Плановый объём работы")
    position: int | None = Field(default=None, ge=1)


class WorkUpdate(SectionUpdate):
    unit_name: str | None = Field(default=None, max_length=50)
    quantity: Decimal | None = Field(default=None, ge=0)
    section_id: int | None = Field(default=None, description="Перенести работу в другой раздел той же сметы")


class PeriodCreate(BaseModel):
    date_from: dt_date
    date_to: dt_date


class PeriodUpdate(BaseModel):
    date_from: dt_date | None = None
    date_to: dt_date | None = None


class ResourceCreate(BaseModel):
    price_item_id: int | None = Field(default=None, description="Позиция справочника ресурсов: вид, название, ед., цена и подрядчик берутся из неё; явно переданные поля важнее")
    type: ResourceType | None = Field(default=None, description="Обязательно, если не задан price_item_id")
    name: str | None = Field(default=None, min_length=1, max_length=255, description="Обязательно, если не задан price_item_id")
    contractor_id: str | None = None
    quantity: Decimal = Field(default=Decimal(0), ge=0)
    unit_name: str | None = Field(default=None, max_length=50)
    unit_price: Decimal = Field(default=Decimal(0), ge=0, description="Цена ед. (закупочная)")
    markup_percent: Decimal = Field(default=Decimal(0), ge=0, description="Наценка, %")
    position: int | None = Field(default=None, ge=1)


class ResourceUpdate(BaseModel):
    type: ResourceType | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    contractor_id: str | None = None
    quantity: Decimal | None = Field(default=None, ge=0)
    unit_name: str | None = Field(default=None, max_length=50)
    unit_price: Decimal | None = Field(default=None, ge=0)
    markup_percent: Decimal | None = Field(default=None, ge=0)
    position: int | None = Field(default=None, ge=1)


class SaveToCatalog(BaseModel):
    folder_id: int | None = Field(default=None, description="Папка справочника; null - в корень")


class ProgressCreate(BaseModel):
    date: dt_date = Field(description="День, когда выполнено (не позже сегодняшнего)")
    quantity: Decimal = Field(gt=0, description="Сколько выполнено за этот день")
    contractor_id: str | None = Field(default=None, description="Подрядчик (контрагент), который выполнил")
    comment: str | None = Field(default=None, max_length=500)


class ProgressUpdate(BaseModel):
    date: dt_date | None = None
    quantity: Decimal | None = Field(default=None, gt=0)
    contractor_id: str | None = Field(default=None, description="null - снять подрядчика")
    comment: str | None = Field(default=None, max_length=500)


ACT_KINDS = {"customer": "С заказчиком", "contractor": "С подрядчиком"}
ACT_STATUSES = {"unsigned": "Не подписан", "signed": "Подписан"}
ActKind = Literal["customer", "contractor"]


class EstimateAct(SupplyBase):
    __tablename__ = "estimate_acts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    estimate_id = Column(Integer, ForeignKey("estimates.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(Enum(*ACT_KINDS, name="estimate_act_kind"), nullable=False)
    counterparty_id = Column(CHAR(36), nullable=False, index=True)
    number = Column(Integer, nullable=False)
    date = Column(Date, nullable=False)
    date_from = Column(Date, nullable=False)
    date_to = Column(Date, nullable=False)
    status = Column(Enum(*ACT_STATUSES, name="estimate_act_status"), nullable=False, default="unsigned")
    signed_at = Column(DateTime, nullable=True)
    signed_by = Column(CHAR(36), nullable=True)
    comment = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(CHAR(36), nullable=True)


class EstimateActItem(SupplyBase):
    __tablename__ = "estimate_act_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    act_id = Column(Integer, ForeignKey("estimate_acts.id", ondelete="CASCADE"), nullable=False, index=True)
    work_id = Column(Integer, ForeignKey("estimate_works.id", ondelete="CASCADE"), nullable=False, index=True)
    quantity = Column(Numeric(18, 4), nullable=False)
    unit_price = Column(Numeric(18, 2), nullable=False)
    customer_price = Column(Numeric(18, 2), nullable=True)


class ActItemIn(BaseModel):
    work_id: int
    quantity: Decimal = Field(gt=0, description="Закрываемый объём работы")


class ActCreate(BaseModel):
    date: dt_date = Field(description="Дата акта (можно менять)")
    date_from: dt_date
    date_to: dt_date
    comment: str | None = Field(default=None, max_length=500)
    items: list[ActItemIn] = Field(min_length=1)


class ActUpdate(BaseModel):
    date: dt_date | None = None
    date_from: dt_date | None = None
    date_to: dt_date | None = None
    comment: str | None = Field(default=None, max_length=500)
    items: list[ActItemIn] | None = Field(default=None, min_length=1, description="Полностью заменяет состав акта (только у неподписанного)")
