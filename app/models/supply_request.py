import uuid
from app.database import msk_now
from datetime import date as dt_date
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import CHAR, Boolean, Column, Date, DateTime, Enum, Float, ForeignKey, Integer, Numeric, String, Text

from app.database import SupplyBase


class SupplyRequest(SupplyBase):
    __tablename__ = "request"

    id = Column(Integer, primary_key=True, autoincrement=True)
    object_levels_id = Column(CHAR(36), nullable=False, index=True)
    object_type = Column(Enum("object", "object_levels", name="request_object_type"), nullable=False, server_default="object_levels")
    name = Column(String(200), nullable=True)
    comment = Column(Text, nullable=True)
    created_by = Column(CHAR(36), nullable=False, index=True)
    executor = Column(CHAR(36), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    started_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    deadline = Column(DateTime, nullable=True)
    status_id = Column(CHAR(36), ForeignKey("status.id"), nullable=False, index=True)
    copied_from_request_id = Column(Integer, nullable=True)
    split_from_request_id = Column(Integer, nullable=True)
    split_to_request_ids = Column(Text, nullable=True)
    items_count_before_split = Column(Integer, nullable=True)


class RequestItem(SupplyBase):
    __tablename__ = "request_items"

    id = Column(CHAR(36), primary_key=True)
    request_id = Column(Integer, ForeignKey("request.id"), nullable=False, index=True)
    num = Column(Integer, nullable=False)
    nomenclature_id = Column(CHAR(36), nullable=True, index=True)
    name = Column(String(400), nullable=True)
    unit_id = Column(CHAR(36), nullable=True, index=True)
    quantity = Column(Numeric(10, 3), nullable=False)
    warehouse_category_id = Column(CHAR(36), nullable=True, index=True)
    comment = Column(Text, nullable=True)
    is_new = Column(Boolean, nullable=False, server_default="0")


class RequestLog(SupplyBase):
    __tablename__ = "request_log"

    id = Column(CHAR(36), primary_key=True)
    user_id = Column(CHAR(36), nullable=False, index=True)
    request_id = Column(String(36), nullable=False, index=True)
    status_name = Column(String(20), nullable=False)
    date_response = Column(DateTime, nullable=True)


class RequestItemSnapshot(SupplyBase):
    __tablename__ = "request_item_snapshot"

    id = Column(CHAR(36), primary_key=True)
    request_id = Column(Integer, ForeignKey("request.id"), nullable=False, index=True)
    request_item_id = Column(CHAR(36), ForeignKey("request_items.id"), nullable=False, index=True)
    original_quantity = Column(Float, nullable=False)
    snapshot_quantity = Column(Float, nullable=False)
    quantity_diff = Column(Float, nullable=False)
    created_by = Column(CHAR(36), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)


class RequestInvoiceLink(SupplyBase):
    __tablename__ = "request_invoice_links"

    id = Column(CHAR(36), primary_key=True)
    request_id = Column(Integer, ForeignKey("request.id"), nullable=False, index=True)
    invoice_id = Column(Integer, nullable=False, index=True)
    created_by = Column(CHAR(36), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)


class RequestEventLog(SupplyBase):
    __tablename__ = "request_event_log"

    id = Column(CHAR(36), primary_key=True)
    request_id = Column(Integer, ForeignKey("request.id"), nullable=False, index=True)
    user_id = Column(CHAR(36), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)


class StatusRef(SupplyBase):
    __tablename__ = "status"

    id = Column(CHAR(36), primary_key=True)
    name = Column(String(200), nullable=False)


class UnitRef(SupplyBase):
    __tablename__ = "unit"

    id = Column(CHAR(36), primary_key=True)
    name = Column(String(200), nullable=False)


class NomenclatureRef(SupplyBase):
    __tablename__ = "nomenclature"

    id = Column(CHAR(36), primary_key=True)
    warehouse_category_id = Column(CHAR(36), nullable=False, index=True)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    article = Column(String(200), nullable=True)
    unit_id = Column(CHAR(36), nullable=False, index=True)
    length = Column(Float, nullable=True)
    width = Column(Float, nullable=True)
    height = Column(Float, nullable=True)
    weight = Column(Float, nullable=True)
    vat_rate = Column(Integer, nullable=True)
    price_opt = Column(Float, nullable=True)
    price_opt2 = Column(Float, nullable=True)
    price_retail = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=True, index=True)


class WarehousePriceHistory(SupplyBase):
    __tablename__ = "warehouse_price_history"

    id = Column(CHAR(36), primary_key=True)
    nomenclature_id = Column(CHAR(36), ForeignKey("nomenclature.id"), nullable=False, index=True)
    type = Column(String(30), nullable=False)
    value = Column(Float, nullable=False)
    date = Column(Date, nullable=False)


class WarehouseCategoryRef(SupplyBase):
    __tablename__ = "warehouse_category"

    id = Column(CHAR(36), primary_key=True)
    name = Column(String(200), nullable=False)
    parent_id = Column(CHAR(36), nullable=True, index=True)


class SupplyRequestCreate(BaseModel):
    object_levels_id: str | None = Field(default=None)
    object_type: Literal["object", "object_levels"] = Field(default="object_levels")
    name: str | None = Field(default=None)
    comment: str | None = Field(default=None)
    executor: str | None = Field(default=None)
    started_at: datetime | None = Field(default=None)
    approved_at: datetime | None = Field(default=None)
    rejected_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)
    deadline: datetime | None = Field(default=None)


class SupplyRequestUpdate(BaseModel):
    object_levels_id: str | None = Field(default=None)
    object_type: Literal["object", "object_levels"] | None = Field(default=None)
    name: str | None = Field(default=None)
    comment: str | None = Field(default=None)
    executor: str | None = Field(default=None)
    started_at: datetime | None = Field(default=None)
    approved_at: datetime | None = Field(default=None)
    rejected_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)
    deadline: datetime | None = Field(default=None)
    status_id: str | None = Field(default=None)


class RequestSplitItem(BaseModel):
    item_id: str
    quantity: float | None = Field(default=None)


class RequestSplit(BaseModel):
    name: str | None = Field(default=None)
    items: list[RequestSplitItem]


class RequestSplitRequest(BaseModel):
    splits: list[RequestSplit]


class RequestItemCreate(BaseModel):
    num: int | None = Field(default=None)
    nomenclature_id: str | None = Field(default=None)
    name: str | None = Field(default=None)
    unit_id: str | None = Field(default=None)
    quantity: float | None = Field(default=1.0)
    warehouse_category_id: str | None = Field(default=None)
    comment: str | None = Field(default=None)


class RequestItemUpdate(BaseModel):
    num: int | None = Field(default=None)
    nomenclature_id: str | None = Field(default=None)
    name: str | None = Field(default=None)
    unit_id: str | None = Field(default=None)
    quantity: float | None = Field(default=None)
    warehouse_category_id: str | None = Field(default=None)
    comment: str | None = Field(default=None)


class NomenclatureCreate(BaseModel):
    warehouse_category_id: str
    name: str
    description: str | None = Field(default=None)
    article: str | None = Field(default=None)
    unit_id: str
    length: float | None = Field(default=None)
    width: float | None = Field(default=None)
    height: float | None = Field(default=None)
    weight: float | None = Field(default=None)
    vat_rate: int | None = Field(default=None)
    price_opt: float | None = Field(default=None)
    price_opt2: float | None = Field(default=None)
    price_retail: float | None = Field(default=None)


class NomenclatureUpdate(BaseModel):
    warehouse_category_id: str | None = Field(default=None)
    name: str | None = Field(default=None)
    description: str | None = Field(default=None)
    article: str | None = Field(default=None)
    unit_id: str | None = Field(default=None)
    length: float | None = Field(default=None)
    width: float | None = Field(default=None)
    height: float | None = Field(default=None)
    weight: float | None = Field(default=None)
    vat_rate: int | None = Field(default=None)
    price_opt: float | None = Field(default=None)
    price_opt2: float | None = Field(default=None)
    price_retail: float | None = Field(default=None)


class WarehousePriceHistoryCreate(BaseModel):
    nomenclature_id: str
    type: Literal["price_purchase", "price_opt", "price_opt2", "price_retail"]
    value: float
    date: dt_date


class WarehousePriceHistoryUpdate(BaseModel):
    nomenclature_id: str | None = Field(default=None)
    type: Literal["price_purchase", "price_opt", "price_opt2", "price_retail"] | None = Field(default=None)
    value: float | None = Field(default=None)
    date: dt_date | None = Field(default=None)


class WarehouseCategoryCreate(BaseModel):
    name: str
    parent_id: str | None = Field(default=None)


class WarehouseCategoryUpdate(BaseModel):
    name: str | None = Field(default=None)
    parent_id: str | None = Field(default=None)


class UnitCreate(BaseModel):
    name: str


class RequestApproverCreate(BaseModel):
    user_id: str
    status_name: Literal["pending", "approved", "rejected"] = Field(default="pending")
    date_response: datetime | None = Field(default=None)


class RequestApproverUpdate(BaseModel):
    user_id: str | None = Field(default=None)
    status_name: Literal["pending", "approved", "rejected"] | None = Field(default=None)
    date_response: datetime | None = Field(default=None)


class NomenclatureSimilar(SupplyBase):
    __tablename__ = "nomenclature_similar"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nomenclature_id = Column(CHAR(36), nullable=False, index=True)
    nomenclature_simmilar_id = Column(CHAR(36), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)


class NomenclatureSimilarCreate(BaseModel):
    nomenclature_id: str
    nomenclature_simmilar_id: str


class NomenclatureSimilarUpdate(BaseModel):
    nomenclature_simmilar_id: str | None = Field(default=None)


class NomenclatureUserSimilar(SupplyBase):
    __tablename__ = "nomenclature_user_simmilar"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nomenclature_id = Column(CHAR(36), nullable=False, index=True)
    user_id = Column(CHAR(36), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)


class NomenclatureUserSimilarCreate(BaseModel):
    nomenclature_id: str


class NomenclatureUserSimilarUpdate(BaseModel):
    nomenclature_id: str | None = Field(default=None)


class NomenclatureCompetitor(SupplyBase):
    __tablename__ = "nomenclature_competitors"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nomenclature_id = Column(CHAR(36), nullable=False, index=True)
    name = Column(Text, nullable=False)
    price = Column(Float(17, 8), nullable=False)
    source_name = Column(Text, nullable=True)
    source_site = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)


class NomenclatureCompetitorCreate(BaseModel):
    nomenclature_id: str
    name: str
    price: float
    source_name: str | None = Field(default=None)
    source_site: str | None = Field(default=None)


class NomenclatureCompetitorUpdate(BaseModel):
    name: str | None = Field(default=None)
    price: float | None = Field(default=None)
    source_name: str | None = Field(default=None)
    source_site: str | None = Field(default=None)


class NomenclatureCompetitorFile(SupplyBase):
    __tablename__ = "nomenclature_competitor_files"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nomenclature_competitor_id = Column(CHAR(36), nullable=True, index=True)
    original_name = Column(Text, nullable=True)
    storage_name = Column(Text, nullable=True)
    extension = Column(String(100), nullable=True)
    file_path = Column(Text, nullable=True)
    uploaded_by = Column(CHAR(36), nullable=False, index=True)
    uploaded_at = Column(DateTime, nullable=False, default=msk_now)


class NomenclatureAgreement(SupplyBase):
    __tablename__ = "nomenclature_agreement"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nomenclature_id = Column(CHAR(36), nullable=False, index=True)
    agreement = Column(Boolean, nullable=False)
    type = Column(Enum("director", "magazine"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)


class NomenclatureAgreementCreate(BaseModel):
    nomenclature_id: str
    agreement: bool
    type: Literal["director", "magazine"]


class NomenclatureAgreementUpdate(BaseModel):
    agreement: bool | None = Field(default=None)
    type: Literal["director", "magazine"] | None = Field(default=None)


class NomenclatureFeedback(SupplyBase):
    __tablename__ = "nomenclature_feedback"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nomenclature_id = Column(CHAR(36), nullable=False, index=True)
    star = Column(Integer, nullable=False)
    comment = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)


class NomenclatureFeedbackCreate(BaseModel):
    nomenclature_id: str
    star: int
    comment: str


class NomenclatureFeedbackUpdate(BaseModel):
    star: int | None = Field(default=None)
    comment: str | None = Field(default=None)


class NomenclatureFeedbackFile(SupplyBase):
    __tablename__ = "nomenclature_feedback_files"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nomenclature_feedback_id = Column(CHAR(36), nullable=False, index=True)
    original_name = Column(Text, nullable=True)
    storage_name = Column(Text, nullable=True)
    extension = Column(String(100), nullable=True)
    file_path = Column(Text, nullable=True)
    uploaded_by = Column(CHAR(36), nullable=False, index=True)
    uploaded_at = Column(DateTime, nullable=False, default=msk_now)


class NomenclatureGroup(SupplyBase):
    __tablename__ = "nomenclature_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(300), nullable=False)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)


class NomenclatureGroupCreate(BaseModel):
    name: str


class NomenclatureGroupUpdate(BaseModel):
    name: str | None = Field(default=None)


class NomenclatureGroupItem(SupplyBase):
    __tablename__ = "nomenclature_group_items"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nomenclature_group_id = Column(Integer, nullable=False, index=True)
    nomenclature_id = Column(CHAR(36), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)
    created_by = Column(CHAR(36), nullable=False, index=True)


class RequestItemSnapshotCreate(BaseModel):
    request_item_id: str
    original_quantity: float
    snapshot_quantity: float
    quantity_diff: float


class RequestEventLogCreate(BaseModel):
    request_id: int
    event_type: str
    description: str | None = Field(default=None)
    metadata_json: str | None = Field(default=None)
