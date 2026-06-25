import uuid
from types import SimpleNamespace

from sqlalchemy import bindparam, distinct, text
from sqlalchemy.orm import Session

from app.models.supply_request import NomenclatureRef, StatusRef, UnitRef
from app.models.warehouse import Warehouse
from app.models.request_file import FileAudit, FileDB, FileType
from app.models.warehouse_receipt import (
    WarehouseFile,
    WarehouseReceipt,
    WarehouseReceiptItem,
    WarehouseReceiptItemLog,
    WarehouseReceiptLog,
)


class WarehouseReceiptRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._table_columns_cache: dict[str, set[str]] = {}

    def get_receipts(self) -> list[WarehouseReceipt]:
        return self.db.query(WarehouseReceipt).order_by(WarehouseReceipt.created_at.desc()).all()

    def get_receipts_by_type(self, receipt_type: int, warehouse_id: str | None = None) -> list[WarehouseReceipt]:
        query = self.db.query(WarehouseReceipt).filter(WarehouseReceipt.type == receipt_type)
        if warehouse_id:
            query = query.filter(WarehouseReceipt.warehouse_id == warehouse_id)
        return query.order_by(WarehouseReceipt.created_at.desc()).all()

    def get_receipt_by_id(self, receipt_id: str) -> WarehouseReceipt | None:
        return self.db.query(WarehouseReceipt).filter(WarehouseReceipt.id == receipt_id).first()

    def get_inventory_snapshot(self, nomenclature_id: str, warehouse_id: str | None) -> dict:
        total_quantity_query = "SELECT COALESCE(SUM(quantity), 0) AS total_quantity FROM warehouse_list WHERE nomenclature_id = :nomenclature_id"
        last_price_query = (
            "SELECT price FROM warehouse_list "
            "WHERE nomenclature_id = :nomenclature_id AND price IS NOT NULL"
        )
        params = {"nomenclature_id": nomenclature_id}
        if warehouse_id:
            total_quantity_query += " AND warehouse_id = :warehouse_id"
            last_price_query += " AND warehouse_id = :warehouse_id"
            params["warehouse_id"] = warehouse_id
        last_price_query += " ORDER BY date DESC, id DESC LIMIT 1"

        total_quantity_row = self.db.execute(text(total_quantity_query), params).mappings().first()
        last_price_row = self.db.execute(text(last_price_query), params).mappings().first()
        return {
            "total_quantity": float(total_quantity_row["total_quantity"]) if total_quantity_row else 0.0,
            "last_price": float(last_price_row["price"]) if last_price_row and last_price_row.get("price") is not None else None,
        }

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

    def get_receipt_logs(self, receipt_id: str) -> list[WarehouseReceiptLog]:
        return (
            self.db.query(WarehouseReceiptLog)
            .filter(WarehouseReceiptLog.warehouse_receipt_id == receipt_id)
            .order_by(WarehouseReceiptLog.id.desc())
            .all()
        )

    def get_receipt_log_by_id(self, receipt_id: str, log_id: int) -> WarehouseReceiptLog | None:
        return (
            self.db.query(WarehouseReceiptLog)
            .filter(
                WarehouseReceiptLog.warehouse_receipt_id == receipt_id,
                WarehouseReceiptLog.id == log_id,
            )
            .first()
        )

    def create_receipt_log(self, receipt_id: str, payload: dict) -> WarehouseReceiptLog:
        row = WarehouseReceiptLog(warehouse_receipt_id=receipt_id, **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_receipt_log(self, row: WarehouseReceiptLog) -> WarehouseReceiptLog:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_receipt_log(self, row: WarehouseReceiptLog) -> None:
        self.db.delete(row)
        self.db.commit()

    def get_receipt_item_logs(self, item_id: str) -> list[WarehouseReceiptItemLog]:
        return (
            self.db.query(WarehouseReceiptItemLog)
            .filter(WarehouseReceiptItemLog.warehouse_receipt_item_id == item_id)
            .order_by(WarehouseReceiptItemLog.id.desc())
            .all()
        )

    def get_receipt_item_log_by_id(self, item_id: str, log_id: int) -> WarehouseReceiptItemLog | None:
        return (
            self.db.query(WarehouseReceiptItemLog)
            .filter(
                WarehouseReceiptItemLog.warehouse_receipt_item_id == item_id,
                WarehouseReceiptItemLog.id == log_id,
            )
            .first()
        )

    def create_receipt_item_log(self, item_id: str, payload: dict) -> WarehouseReceiptItemLog:
        row = WarehouseReceiptItemLog(warehouse_receipt_item_id=item_id, **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_receipt_item_log(self, row: WarehouseReceiptItemLog) -> WarehouseReceiptItemLog:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_receipt_item_log(self, row: WarehouseReceiptItemLog) -> None:
        self.db.delete(row)
        self.db.commit()

    def get_unique_receipt_parties(self) -> list[str]:
        rows = (
            self.db.query(
                distinct(
                    WarehouseReceipt.to_id
                )
            )
            .filter(
                WarehouseReceipt.type == 1,
                WarehouseReceipt.to_id.isnot(None),
                WarehouseReceipt.to_id != "",
            )
            .all()
        )
        from_rows = (
            self.db.query(
                distinct(
                    WarehouseReceipt.from_id
                )
            )
            .filter(
                WarehouseReceipt.type == 2,
                WarehouseReceipt.from_id.isnot(None),
                WarehouseReceipt.from_id != "",
            )
            .all()
        )
        return sorted({value for (value,) in rows + from_rows if value})

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

    def get_nomenclature(self, nomenclature_ids: list[str]) -> dict[str, SimpleNamespace]:
        unique_ids = list({nomenclature_id for nomenclature_id in nomenclature_ids if nomenclature_id})
        if not unique_ids:
            return {}
        available_columns = self._get_table_columns("nomenclature")
        select_columns = [
            "id",
            "warehouse_category_id",
            "name",
            "description",
            "article",
            "unit_id",
            "length",
            "width",
            "height",
            "weight",
            "vat_rate",
            "price_opt",
            "price_opt2",
            "price_retail",
            "created_at",
            "created_by",
        ]
        filtered_columns = [column for column in select_columns if column in available_columns]
        query = text(
            "SELECT "
            + ", ".join(f"`{column}`" for column in filtered_columns)
            + " FROM `nomenclature` WHERE `id` IN :ids"
        ).bindparams(bindparam("ids", expanding=True))
        rows = self.db.execute(query, {"ids": unique_ids}).mappings().all()
        result: dict[str, SimpleNamespace] = {}
        for row in rows:
            payload = {column: row.get(column) for column in filtered_columns}
            payload.setdefault("vat_rate", None)
            payload.setdefault("price_opt", None)
            payload.setdefault("price_opt2", None)
            payload.setdefault("price_retail", None)
            result[payload["id"]] = SimpleNamespace(**payload)
        return result

    def get_units(self, unit_ids: list[str]) -> dict[str, UnitRef]:
        unique_ids = list({unit_id for unit_id in unit_ids if unit_id})
        if not unique_ids:
            return {}
        rows = self.db.query(UnitRef).filter(UnitRef.id.in_(unique_ids)).all()
        return {row.id: row for row in rows}

    def get_file_type_by_code(self, code: str) -> FileType | None:
        return (
            self.db.query(FileType)
            .filter(
                FileType.code == code,
                FileType.is_active.is_(True),
            )
            .first()
        )

    def create_warehouse_file_link(self, row: WarehouseFile) -> WarehouseFile:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def create_file_and_warehouse_link(self, file_row: FileDB, warehouse_file_row: WarehouseFile) -> FileDB:
        self.db.add(file_row)
        self.db.add(warehouse_file_row)
        self.db.commit()
        self.db.refresh(file_row)
        return file_row

    def get_warehouse_files(self, receipt_id: str):
        return (
            self.db.query(WarehouseFile, FileDB, FileType)
            .join(FileDB, FileDB.id == WarehouseFile.file_id)
            .join(FileType, FileType.id == FileDB.file_type_id)
            .filter(
                WarehouseFile.warehouse_receipt_id == receipt_id,
                FileDB.status == "active",
            )
            .order_by(WarehouseFile.created_at.desc())
            .all()
        )

    def get_warehouse_file(self, receipt_id: str, file_id: str):
        return (
            self.db.query(WarehouseFile, FileDB, FileType)
            .join(FileDB, FileDB.id == WarehouseFile.file_id)
            .join(FileType, FileType.id == FileDB.file_type_id)
            .filter(
                WarehouseFile.warehouse_receipt_id == receipt_id,
                WarehouseFile.file_id == file_id,
                FileDB.status == "active",
            )
            .first()
        )

    def get_file_by_id(self, file_id: str) -> FileDB | None:
        return (
            self.db.query(FileDB)
            .filter(
                FileDB.id == file_id,
                FileDB.status == "active",
            )
            .first()
        )

    def mark_file_deleted(self, file_row: FileDB) -> None:
        file_row.status = "deleted"
        self.db.commit()

    def add_audit(self, audit: FileAudit) -> None:
        self.db.add(audit)
        self.db.commit()

    def _get_table_columns(self, table_name: str) -> set[str]:
        cached = self._table_columns_cache.get(table_name)
        if cached is not None:
            return cached
        rows = self.db.execute(text(f"SHOW COLUMNS FROM `{table_name}`")).mappings().all()
        columns = {row["Field"] for row in rows}
        self._table_columns_cache[table_name] = columns
        return columns
