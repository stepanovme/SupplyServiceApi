import uuid
from types import SimpleNamespace

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.delivery import Delivery, DeliveryItem
from app.models.delivery_item_mapping import DeliveryItemMapping
from app.models.invoice import Invoice, InvoiceItem
from app.models.supply_request import NomenclatureRef, SupplyRequest, UnitRef, WarehouseCategoryRef, WarehousePriceHistory
from app.models.upd_document import UpdDocument, UpdDocumentItem
from app.models.upd_item_mapping import UpdItemMapping
from app.models.warehouse import WarehouseList
from app.models.warehouse_receipt import WarehouseReceipt, WarehouseReceiptItem, WarehouseReceiptItemLog, WarehouseReceiptLog


class CatalogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._table_columns_cache: dict[str, set[str]] = {}

    def get_units(self) -> list[UnitRef]:
        return self.db.query(UnitRef).order_by(UnitRef.name.asc()).all()

    def create_unit(self, payload: dict) -> UnitRef:
        item = UnitRef(
            id=str(uuid.uuid4()),
            **payload,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_warehouse_categories(self) -> list[WarehouseCategoryRef]:
        return self.db.query(WarehouseCategoryRef).order_by(WarehouseCategoryRef.name.asc()).all()

    def get_warehouse_category_by_id(self, category_id: str) -> WarehouseCategoryRef | None:
        return self.db.query(WarehouseCategoryRef).filter(WarehouseCategoryRef.id == category_id).first()

    def create_warehouse_category(self, payload: dict) -> WarehouseCategoryRef:
        item = WarehouseCategoryRef(
            id=str(uuid.uuid4()),
            **payload,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def save_warehouse_category(self, item: WarehouseCategoryRef) -> WarehouseCategoryRef:
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_nomenclature(self, search: str | None = None) -> list[object]:
        columns = self._get_table_columns("nomenclature")
        select_columns = [
            "id",
            "warehouse_category_id",
            "name",
            "unit_id",
        ]
        optional_columns = [
            "description",
            "article",
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
        select_columns.extend([column for column in optional_columns if column in columns])
        sql = (
            f"SELECT {', '.join(select_columns)} "
            "FROM nomenclature "
        )
        params = {}
        if search:
            sql += "WHERE name LIKE :search "
            params["search"] = f"%{search}%"
        if "created_at" in columns:
            sql += "ORDER BY created_at DESC"
        else:
            sql += "ORDER BY id DESC"
        rows = self.db.execute(text(sql), params).mappings().all()
        return [self._build_nomenclature_namespace(row) for row in rows]

    def get_nomenclature_by_id(self, nomenclature_id: str) -> object | None:
        columns = self._get_table_columns("nomenclature")
        select_columns = [
            "id",
            "warehouse_category_id",
            "name",
            "unit_id",
        ]
        optional_columns = [
            "description",
            "article",
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
        select_columns.extend([column for column in optional_columns if column in columns])
        row = self.db.execute(
            text(
                f"SELECT {', '.join(select_columns)} "
                "FROM nomenclature "
                "WHERE id = :nomenclature_id "
                "LIMIT 1"
            ),
            {"nomenclature_id": nomenclature_id},
        ).mappings().first()
        return self._build_nomenclature_namespace(row) if row else None

    def create_nomenclature(self, payload: dict) -> NomenclatureRef:
        columns = self._get_table_columns("nomenclature")
        row_id = str(uuid.uuid4())
        insert_payload = {"id": row_id}
        insert_payload.update({key: value for key, value in payload.items() if key in columns})
        query = text(
            "INSERT INTO nomenclature ("
            + ", ".join(insert_payload.keys())
            + ") VALUES ("
            + ", ".join(f":{key}" for key in insert_payload.keys())
            + ")"
        )
        self.db.execute(query, insert_payload)
        self.db.commit()
        return self.get_nomenclature_by_id(row_id)

    def save_nomenclature(self, nomenclature_id: str, payload: dict):
        columns = self._get_table_columns("nomenclature")
        update_payload = {key: value for key, value in payload.items() if key in columns}
        if update_payload:
            assignments = ", ".join(f"{key} = :{key}" for key in update_payload.keys())
            query = text(f"UPDATE nomenclature SET {assignments} WHERE id = :nomenclature_id")
            self.db.execute(query, {**update_payload, "nomenclature_id": nomenclature_id})
            self.db.commit()
        return self.get_nomenclature_by_id(nomenclature_id)

    def delete_nomenclature(self, nomenclature_id: str) -> None:
        self.db.execute(text("DELETE FROM nomenclature WHERE id = :nomenclature_id"), {"nomenclature_id": nomenclature_id})
        self.db.commit()

    def get_price_rows_by_nomenclature(self, nomenclature_id: str) -> list[WarehouseList]:
        return (
            self.db.query(WarehouseList)
            .filter(
                WarehouseList.nomenclature_id == nomenclature_id,
                WarehouseList.price.isnot(None),
            )
            .order_by(WarehouseList.date.asc(), WarehouseList.id.asc())
            .all()
        )

    def get_warehouse_list_history_by_nomenclature(self, nomenclature_id: str) -> list[WarehouseList]:
        return (
            self.db.query(WarehouseList)
            .filter(
                WarehouseList.nomenclature_id == nomenclature_id,
                WarehouseList.upd_item_mapping_id.isnot(None),
            )
            .order_by(WarehouseList.date.desc(), WarehouseList.id.desc())
            .all()
        )

    def get_receipt_items_by_nomenclature(self, nomenclature_id: str) -> list[WarehouseReceiptItem]:
        return (
            self.db.query(WarehouseReceiptItem)
            .filter(WarehouseReceiptItem.nomenclature_id == nomenclature_id)
            .order_by(WarehouseReceiptItem.id.desc())
            .all()
        )

    def get_warehouse_receipts_by_ids(self, receipt_ids: list[str]) -> dict[str, WarehouseReceipt]:
        unique_ids = list({receipt_id for receipt_id in receipt_ids if receipt_id})
        if not unique_ids:
            return {}
        rows = self.db.query(WarehouseReceipt).filter(WarehouseReceipt.id.in_(unique_ids)).all()
        return {row.id: row for row in rows}

    def get_warehouse_receipt_item_logs_by_item_ids(self, item_ids: list[str]) -> dict[str, list[WarehouseReceiptItemLog]]:
        unique_ids = list({item_id for item_id in item_ids if item_id})
        if not unique_ids:
            return {}
        rows = (
            self.db.query(WarehouseReceiptItemLog)
            .filter(WarehouseReceiptItemLog.warehouse_receipt_item_id.in_(unique_ids))
            .order_by(WarehouseReceiptItemLog.created_at.desc(), WarehouseReceiptItemLog.id.desc())
            .all()
        )
        grouped: dict[str, list[WarehouseReceiptItemLog]] = {}
        for row in rows:
            grouped.setdefault(row.warehouse_receipt_item_id, []).append(row)
        return grouped

    def get_deliveries_by_ids(self, delivery_ids: list[str]) -> dict[str, Delivery]:
        unique_ids = list({delivery_id for delivery_id in delivery_ids if delivery_id})
        if not unique_ids:
            return {}
        rows = self.db.query(Delivery).filter(Delivery.id.in_(unique_ids)).all()
        return {row.id: row for row in rows}

    def get_delivery_items_by_delivery_ids(self, delivery_ids: list[str]) -> list[DeliveryItem]:
        unique_ids = list({delivery_id for delivery_id in delivery_ids if delivery_id})
        if not unique_ids:
            return []
        return (
            self.db.query(DeliveryItem)
            .filter(DeliveryItem.delivery_id.in_(unique_ids))
            .order_by(DeliveryItem.created_at.desc(), DeliveryItem.id.desc())
            .all()
        )

    def get_delivery_item_mappings_by_delivery_ids_and_nomenclature(
        self,
        delivery_ids: list[str],
        nomenclature_id: str,
    ) -> list[DeliveryItemMapping]:
        unique_ids = list({delivery_id for delivery_id in delivery_ids if delivery_id})
        if not unique_ids or not nomenclature_id:
            return []
        return (
            self.db.query(DeliveryItemMapping)
            .filter(
                DeliveryItemMapping.delivery_id.in_(unique_ids),
                DeliveryItemMapping.nomenclature_id == nomenclature_id,
            )
            .order_by(DeliveryItemMapping.created_at.desc(), DeliveryItemMapping.id.desc())
            .all()
        )

    def get_invoices_by_ids(self, invoice_ids: list[int]) -> dict[int, Invoice]:
        unique_ids = list({invoice_id for invoice_id in invoice_ids if invoice_id is not None})
        if not unique_ids:
            return {}
        rows = self.db.query(Invoice).filter(Invoice.id.in_(unique_ids)).all()
        return {row.id: row for row in rows}

    def get_invoice_items_by_ids(self, invoice_item_ids: list[str]) -> dict[str, InvoiceItem]:
        unique_ids = list({item_id for item_id in invoice_item_ids if item_id})
        if not unique_ids:
            return {}
        rows = self.db.query(InvoiceItem).filter(InvoiceItem.id.in_(unique_ids)).all()
        return {row.id: row for row in rows}

    def get_requests_by_ids(self, request_ids: list[int]) -> dict[int, SupplyRequest]:
        unique_ids = list({request_id for request_id in request_ids if request_id is not None})
        if not unique_ids:
            return {}
        rows = self.db.query(SupplyRequest).filter(SupplyRequest.id.in_(unique_ids)).all()
        return {row.id: row for row in rows}

    def get_upd_item_mappings_by_ids(self, mapping_ids: list[str]) -> dict[str, UpdItemMapping]:
        unique_ids = list({mapping_id for mapping_id in mapping_ids if mapping_id})
        if not unique_ids:
            return {}
        rows = self.db.query(UpdItemMapping).filter(UpdItemMapping.id.in_(unique_ids)).all()
        return {row.id: row for row in rows}

    def get_upd_item_mappings_by_document_ids_and_nomenclature(
        self,
        document_ids: list[str],
        nomenclature_id: str,
    ) -> list[UpdItemMapping]:
        unique_ids = list({document_id for document_id in document_ids if document_id})
        if not unique_ids or not nomenclature_id:
            return []
        return (
            self.db.query(UpdItemMapping)
            .filter(
                UpdItemMapping.upd_documents_id.in_(unique_ids),
                UpdItemMapping.nomenclature_id == nomenclature_id,
            )
            .order_by(UpdItemMapping.created_at.desc(), UpdItemMapping.id.desc())
            .all()
        )

    def get_upd_documents_by_ids(self, document_ids: list[str]) -> dict[str, UpdDocument]:
        unique_ids = list({document_id for document_id in document_ids if document_id})
        if not unique_ids:
            return {}
        rows = self.db.query(UpdDocument).filter(UpdDocument.id.in_(unique_ids)).all()
        return {row.id: row for row in rows}

    def get_upd_document_items_by_ids(self, item_ids: list[str]) -> dict[str, UpdDocumentItem]:
        unique_ids = list({item_id for item_id in item_ids if item_id})
        if not unique_ids:
            return {}
        rows = self.db.query(UpdDocumentItem).filter(UpdDocumentItem.id.in_(unique_ids)).all()
        return {row.id: row for row in rows}

    def get_warehouse_receipts_by_upd_document_ids(self, document_ids: list[str]) -> dict[str, list[WarehouseReceipt]]:
        unique_ids = list({document_id for document_id in document_ids if document_id})
        if not unique_ids:
            return {}
        rows = (
            self.db.query(WarehouseReceipt)
            .filter(
                WarehouseReceipt.upd_documents_id.in_(unique_ids),
                WarehouseReceipt.type == 1,
            )
            .order_by(WarehouseReceipt.created_at.desc(), WarehouseReceipt.id.desc())
            .all()
        )
        grouped: dict[str, list[WarehouseReceipt]] = {}
        for row in rows:
            grouped.setdefault(row.upd_documents_id, []).append(row)
        return grouped

    def get_warehouse_receipt_logs_by_receipt_ids(self, receipt_ids: list[str]) -> dict[str, list[WarehouseReceiptLog]]:
        unique_ids = list({receipt_id for receipt_id in receipt_ids if receipt_id})
        if not unique_ids:
            return {}
        rows = (
            self.db.query(WarehouseReceiptLog)
            .filter(WarehouseReceiptLog.warehouse_receipt_id.in_(unique_ids))
            .order_by(WarehouseReceiptLog.id.desc())
            .all()
        )
        grouped: dict[str, list[WarehouseReceiptLog]] = {}
        for row in rows:
            grouped.setdefault(row.warehouse_receipt_id, []).append(row)
        return grouped

    def get_price_history(
        self,
        nomenclature_id: str,
        price_type: str | None = None,
    ) -> list[WarehousePriceHistory]:
        query = self.db.query(WarehousePriceHistory).filter(WarehousePriceHistory.nomenclature_id == nomenclature_id)
        if price_type:
            query = query.filter(WarehousePriceHistory.type == price_type)
        return query.order_by(WarehousePriceHistory.date.asc(), WarehousePriceHistory.id.asc()).all()

    def get_price_history_row_by_id(self, row_id: str) -> WarehousePriceHistory | None:
        return self.db.query(WarehousePriceHistory).filter(WarehousePriceHistory.id == row_id).first()

    def create_price_history(self, payload: dict) -> WarehousePriceHistory:
        row = WarehousePriceHistory(id=str(uuid.uuid4()), **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_price_history(self, row: WarehousePriceHistory) -> WarehousePriceHistory:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_price_history(self, row: WarehousePriceHistory) -> None:
        self.db.delete(row)
        self.db.commit()

    def _get_table_columns(self, table_name: str) -> set[str]:
        if table_name in self._table_columns_cache:
            return self._table_columns_cache[table_name]
        try:
            rows = self.db.execute(text(f"SHOW COLUMNS FROM {table_name}")).mappings().all()
            columns = {str(row["Field"]) for row in rows}
        except Exception:
            columns = set()
        self._table_columns_cache[table_name] = columns
        return columns

    @staticmethod
    def _build_nomenclature_namespace(row) -> object:
        return SimpleNamespace(
            id=row.get("id"),
            warehouse_category_id=row.get("warehouse_category_id"),
            name=row.get("name"),
            description=row.get("description"),
            article=row.get("article"),
            unit_id=row.get("unit_id"),
            length=row.get("length"),
            width=row.get("width"),
            height=row.get("height"),
            weight=row.get("weight"),
            vat_rate=row.get("vat_rate"),
            price_opt=row.get("price_opt"),
            price_opt2=row.get("price_opt2"),
            price_retail=row.get("price_retail"),
            created_at=row.get("created_at"),
            created_by=row.get("created_by"),
        )
