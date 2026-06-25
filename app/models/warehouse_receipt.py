import uuid
from datetime import date as dt_date
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, CHAR, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text

from app.database import SupplyBase


class WarehouseReceipt(SupplyBase):
    __tablename__ = "warehouse_receipt"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    num = Column(Integer, nullable=False)
    from_id = Column("from", String(100), nullable=True, index=True)
    to_id = Column("receipt_to", String(100), nullable=True, index=True)
    type = Column(Integer, nullable=True, index=True)
    area_name = Column(Text, nullable=True)
    document = Column(Text, nullable=True)
    who_write_off = Column(CHAR(36), nullable=True, index=True)
    object_id = Column(CHAR(36), nullable=True, index=True)
    file_id = Column(CHAR(36), ForeignKey("files.id"), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    date_arrival = Column(Date, nullable=True)
    date_completed = Column(DateTime, nullable=True)
    warehouse_id = Column(CHAR(36), ForeignKey("warehouse.id"), nullable=False, index=True)
    delivery_id = Column(CHAR(36), nullable=True, index=True)
    toll = Column(Boolean, nullable=False, default=False)
    toll_company_id = Column(CHAR(36), nullable=True, index=True)
    status_id = Column(CHAR(36), ForeignKey("status.id"), nullable=False, index=True)
    upd_documents_id = Column(CHAR(36), ForeignKey("upd_documents.id"), nullable=True, index=True)
    retail = Column(Boolean, nullable=True, default=False)


class WarehouseReceiptItem(SupplyBase):
    __tablename__ = "warehouse_receipt_item"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    warehouse_receipt_id = Column(
        CHAR(36),
        ForeignKey("warehouse_receipt.id"),
        nullable=False,
        index=True,
    )
    nomenclature_id = Column(CHAR(36), ForeignKey("nomenclature.id"), nullable=False, index=True)
    quantity = Column(Float, nullable=True)
    price = Column(Float, nullable=False)
    price_opt = Column(Float, nullable=True)
    price_opt2 = Column(Float, nullable=True)
    price_retail = Column(Float, nullable=True)
    upd_item_mapping = Column(CHAR(36), nullable=True, index=True)
    object_id = Column(CHAR(36), nullable=True, index=True)
    comment = Column(Text, nullable=True)
    attribute = Column(Text, nullable=True)


class WarehouseReceiptLog(SupplyBase):
    __tablename__ = "warehouse_receipt_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    warehouse_id = Column(CHAR(36), ForeignKey("warehouse.id"), nullable=False, index=True)
    warehouse_receipt_id = Column(CHAR(36), ForeignKey("warehouse_receipt.id"), nullable=False, index=True)
    created_at = Column("carated_at", DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(CHAR(36), nullable=False, index=True)


class WarehouseReceiptItemLog(SupplyBase):
    __tablename__ = "warehouse_receipt_item_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    warehouse_receipt_item_id = Column(
        CHAR(36),
        ForeignKey("warehouse_receipt_item.id"),
        nullable=False,
        index=True,
    )
    warehouse_id = Column(CHAR(36), ForeignKey("warehouse.id"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(CHAR(36), nullable=False, index=True)


class WarehouseFile(SupplyBase):
    __tablename__ = "warehouse_file"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    warehouse_receipt_id = Column(
        CHAR(36),
        ForeignKey("warehouse_receipt.id"),
        nullable=False,
        index=True,
    )
    file_id = Column(CHAR(36), ForeignKey("files.id"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=True, default=datetime.utcnow)


class WarehouseReceiptCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    num: int | None = Field(default=None)
    from_id: str | None = Field(default=None, alias="from")
    to_id: str | None = Field(default=None, alias="to")
    type: int | None = Field(default=None)
    area_name: str | None = Field(default=None)
    document: str | None = Field(default=None)
    who_write_off: str | None = Field(default=None)
    object_id: str | None = Field(default=None)
    file_id: str | None = Field(default=None)
    date_arrival: dt_date | None = Field(default=None)
    date_completed: datetime | None = Field(default=None)
    warehouse_id: str | None = Field(default=None)
    delivery_id: str | None = Field(default=None)
    toll: bool | None = Field(default=False)
    toll_company_id: str | None = Field(default=None)
    status_id: str | None = Field(default=None)
    upd_documents_id: str | None = Field(default=None)
    retail: bool | None = Field(default=False)


class WarehouseReceiptUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    num: int | None = Field(default=None)
    from_id: str | None = Field(default=None, alias="from")
    to_id: str | None = Field(default=None, alias="to")
    type: int | None = Field(default=None)
    area_name: str | None = Field(default=None)
    document: str | None = Field(default=None)
    who_write_off: str | None = Field(default=None)
    object_id: str | None = Field(default=None)
    file_id: str | None = Field(default=None)
    date_arrival: dt_date | None = Field(default=None)
    date_completed: datetime | None = Field(default=None)
    warehouse_id: str | None = Field(default=None)
    delivery_id: str | None = Field(default=None)
    toll: bool | None = Field(default=None)
    toll_company_id: str | None = Field(default=None)
    status_id: str | None = Field(default=None)
    upd_documents_id: str | None = Field(default=None)
    retail: bool | None = Field(default=None)


class WarehouseReceiptItemCreate(BaseModel):
    nomenclature_id: str
    quantity: float | None = Field(default=None)
    price: float | None = Field(default=None)
    price_opt: float | None = Field(default=None)
    price_opt2: float | None = Field(default=None)
    price_retail: float | None = Field(default=None)
    upd_item_mapping: str | None = Field(default=None)
    object_id: str | None = Field(default=None)
    comment: str | None = Field(default=None)
    attribute: str | None = Field(default=None)


class WarehouseReceiptItemUpdate(BaseModel):
    nomenclature_id: str | None = Field(default=None)
    quantity: float | None = Field(default=None)
    price: float | None = Field(default=None)
    price_opt: float | None = Field(default=None)
    price_opt2: float | None = Field(default=None)
    price_retail: float | None = Field(default=None)
    upd_item_mapping: str | None = Field(default=None)
    object_id: str | None = Field(default=None)
    comment: str | None = Field(default=None)
    attribute: str | None = Field(default=None)


class WarehouseReceiptLogCreate(BaseModel):
    warehouse_id: str


class WarehouseReceiptLogUpdate(BaseModel):
    warehouse_id: str | None = Field(default=None)


class WarehouseReceiptItemLogCreate(BaseModel):
    warehouse_id: str


class WarehouseReceiptItemLogUpdate(BaseModel):
    warehouse_id: str | None = Field(default=None)
