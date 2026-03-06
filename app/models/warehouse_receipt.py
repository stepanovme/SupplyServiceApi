import uuid
from datetime import date as dt_date
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import CHAR, Column, Date, DateTime, Float, ForeignKey, Integer

from app.database import SupplyBase


class WarehouseReceipt(SupplyBase):
    __tablename__ = "warehouse_receipt"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    num = Column(Integer, nullable=False)
    from_id = Column("from", CHAR(36), nullable=True, index=True)
    object_id = Column(CHAR(36), nullable=True, index=True)
    file_id = Column(CHAR(36), ForeignKey("files.id"), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    date_arrival = Column(Date, nullable=True)
    date_completed = Column(DateTime, nullable=True)
    warehouse_id = Column(CHAR(36), ForeignKey("warehouse.id"), nullable=False, index=True)
    delivery_id = Column(Integer, nullable=True, index=True)
    status_id = Column(CHAR(36), ForeignKey("status.id"), nullable=False, index=True)


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
    object_id = Column(CHAR(36), nullable=True, index=True)


class WarehouseReceiptCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    num: int | None = Field(default=None)
    from_id: str | None = Field(default=None, alias="from")
    object_id: str | None = Field(default=None)
    file_id: str | None = Field(default=None)
    date_arrival: dt_date | None = Field(default=None)
    date_completed: datetime | None = Field(default=None)
    warehouse_id: str | None = Field(default=None)
    delivery_id: int | None = Field(default=None)
    status_id: str | None = Field(default=None)


class WarehouseReceiptUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    num: int | None = Field(default=None)
    from_id: str | None = Field(default=None, alias="from")
    object_id: str | None = Field(default=None)
    file_id: str | None = Field(default=None)
    date_arrival: dt_date | None = Field(default=None)
    date_completed: datetime | None = Field(default=None)
    warehouse_id: str | None = Field(default=None)
    delivery_id: int | None = Field(default=None)
    status_id: str | None = Field(default=None)


class WarehouseReceiptItemCreate(BaseModel):
    nomenclature_id: str
    quantity: float | None = Field(default=None)
    price: float | None = Field(default=None)
    object_id: str | None = Field(default=None)


class WarehouseReceiptItemUpdate(BaseModel):
    nomenclature_id: str | None = Field(default=None)
    quantity: float | None = Field(default=None)
    price: float | None = Field(default=None)
    object_id: str | None = Field(default=None)
