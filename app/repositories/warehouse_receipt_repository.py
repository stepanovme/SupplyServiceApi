import uuid

from sqlalchemy.orm import Session

from app.models.supply_request import NomenclatureRef, StatusRef
from app.models.warehouse import Warehouse
from app.models.warehouse_receipt import WarehouseReceipt, WarehouseReceiptItem


class WarehouseReceiptRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_receipts(self) -> list[WarehouseReceipt]:
        return self.db.query(WarehouseReceipt).order_by(WarehouseReceipt.created_at.desc()).all()

    def get_receipt_by_id(self, receipt_id: str) -> WarehouseReceipt | None:
        return self.db.query(WarehouseReceipt).filter(WarehouseReceipt.id == receipt_id).first()

    def get_next_receipt_num(self) -> int:
        max_row = self.db.query(WarehouseReceipt.num).order_by(WarehouseReceipt.num.desc()).first()
        return (max_row[0] + 1) if max_row else 1

    def create_receipt(self, payload: dict) -> WarehouseReceipt:
        row = WarehouseReceipt(id=str(uuid.uuid4()), **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_receipt(self, row: WarehouseReceipt) -> WarehouseReceipt:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_receipt(self, row: WarehouseReceipt) -> None:
        self.db.delete(row)
        self.db.commit()

    def get_receipt_items(self, receipt_id: str) -> list[WarehouseReceiptItem]:
        return (
            self.db.query(WarehouseReceiptItem)
            .filter(WarehouseReceiptItem.warehouse_receipt_id == receipt_id)
            .all()
        )

    def get_receipt_items_by_receipt_ids(self, receipt_ids: list[str]) -> list[WarehouseReceiptItem]:
        if not receipt_ids:
            return []
        return (
            self.db.query(WarehouseReceiptItem)
            .filter(WarehouseReceiptItem.warehouse_receipt_id.in_(receipt_ids))
            .all()
        )

    def get_receipt_item_by_id(self, receipt_id: str, item_id: str) -> WarehouseReceiptItem | None:
        return (
            self.db.query(WarehouseReceiptItem)
            .filter(
                WarehouseReceiptItem.warehouse_receipt_id == receipt_id,
                WarehouseReceiptItem.id == item_id,
            )
            .first()
        )

    def create_receipt_item(self, receipt_id: str, payload: dict) -> WarehouseReceiptItem:
        row = WarehouseReceiptItem(
            id=str(uuid.uuid4()),
            warehouse_receipt_id=receipt_id,
            **payload,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_receipt_item(self, row: WarehouseReceiptItem) -> WarehouseReceiptItem:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_receipt_item(self, row: WarehouseReceiptItem) -> None:
        self.db.delete(row)
        self.db.commit()

    def get_status_names(self, status_ids: list[str]) -> dict[str, str]:
        unique_ids = list({status_id for status_id in status_ids if status_id})
        if not unique_ids:
            return {}
        rows = self.db.query(StatusRef.id, StatusRef.name).filter(StatusRef.id.in_(unique_ids)).all()
        return {row_id: row_name for row_id, row_name in rows}

    def get_warehouses(self, warehouse_ids: list[str]) -> dict[str, Warehouse]:
        unique_ids = list({warehouse_id for warehouse_id in warehouse_ids if warehouse_id})
        if not unique_ids:
            return {}
        rows = self.db.query(Warehouse).filter(Warehouse.id.in_(unique_ids)).all()
        return {row.id: row for row in rows}

    def get_nomenclature(self, nomenclature_ids: list[str]) -> dict[str, NomenclatureRef]:
        unique_ids = list({nomenclature_id for nomenclature_id in nomenclature_ids if nomenclature_id})
        if not unique_ids:
            return {}
        rows = self.db.query(NomenclatureRef).filter(NomenclatureRef.id.in_(unique_ids)).all()
        return {row.id: row for row in rows}
