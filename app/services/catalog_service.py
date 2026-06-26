from datetime import date as dt_date
from datetime import datetime as dt_datetime

from fastapi import HTTPException, status

from app.models.supply_request import (
    NomenclatureCreate,
    NomenclatureUpdate,
    UnitCreate,
    WarehousePriceHistoryCreate,
    WarehousePriceHistoryUpdate,
    WarehouseCategoryCreate,
    WarehouseCategoryUpdate,
)
from app.repositories.catalog_repository import CatalogRepository
from app.repositories.request_repository import RequestRepository


class CatalogService:
    def __init__(self, repo: CatalogRepository, request_repo: RequestRepository) -> None:
        self.repo = repo
        self.request_repo = request_repo

    def get_units(self):
        return [{"id": item.id, "name": item.name} for item in self.repo.get_units()]

    def create_unit(self, payload: UnitCreate):
        item = self.repo.create_unit(payload.model_dump(exclude_unset=True))
        return {"id": item.id, "name": item.name}

    def get_warehouse_categories(self):
        return [
            {
                "id": item.id,
                "name": item.name,
                "parent_id": item.parent_id,
            }
            for item in self.repo.get_warehouse_categories()
        ]

    def create_warehouse_category(self, payload: WarehouseCategoryCreate):
        data = payload.model_dump(exclude_unset=True)
        item = self.repo.create_warehouse_category(data)
        return {
            "id": item.id,
            "name": item.name,
            "parent_id": item.parent_id,
        }

    def update_warehouse_category(self, category_id: str, payload: WarehouseCategoryUpdate):
        item = self.repo.get_warehouse_category_by_id(category_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Warehouse category not found",
            )

        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(item, key, value)

        updated = self.repo.save_warehouse_category(item)
        return {
            "id": updated.id,
            "name": updated.name,
            "parent_id": updated.parent_id,
        }

    def get_nomenclature(self, search: str | None = None):
        rows = self.repo.get_nomenclature(search)
        return self._serialize_nomenclature_rows(rows)

    def get_nomenclature_by_id(self, nomenclature_id: str):
        row = self.repo.get_nomenclature_by_id(nomenclature_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nomenclature not found")
        rows = self._serialize_nomenclature_rows([row])
        return rows[0]

    def get_nomenclature_purchase_price_stats(self, nomenclature_id: str):
        nomenclature = self.repo.get_nomenclature_by_id(nomenclature_id)
        if not nomenclature:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nomenclature not found")

        rows = self.repo.get_price_rows_by_nomenclature(nomenclature_id)
        prices = [float(row.price) for row in rows if row.price is not None]
        last_row = rows[-1] if rows else None

        average_price = round(sum(prices) / len(prices), 8) if prices else None
        return {
            "nomenclature_id": nomenclature.id,
            "nomenclature_name": nomenclature.name,
            "last_purchase_price": last_row.price if last_row else None,
            "last_purchase_date": last_row.date if last_row else None,
            "max_purchase_price": max(prices) if prices else None,
            "avg_purchase_price": average_price,
            "min_purchase_price": min(prices) if prices else None,
            "rows_count": len(rows),
        }

    def get_nomenclature_receipt_history(self, nomenclature_id: str):
        nomenclature = self.repo.get_nomenclature_by_id(nomenclature_id)
        if not nomenclature:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nomenclature not found")

        units_by_id = {
            item.id: item
            for item in self.request_repo.get_units_by_ids([nomenclature.unit_id] if nomenclature.unit_id else [])
        }
        unit = units_by_id.get(nomenclature.unit_id) if nomenclature.unit_id else None
        rows = self.repo.get_warehouse_list_history_by_nomenclature(nomenclature_id)
        mappings_by_id = self.repo.get_upd_item_mappings_by_ids([row.upd_item_mapping_id for row in rows])
        documents_by_id = self.repo.get_upd_documents_by_ids(
            [mapping.upd_documents_id for mapping in mappings_by_id.values() if mapping.upd_documents_id]
        )
        document_items_by_id = self.repo.get_upd_document_items_by_ids(
            [mapping.upd_documents_item_id for mapping in mappings_by_id.values() if mapping.upd_documents_item_id]
        )
        receipts_by_document_id = self.repo.get_warehouse_receipts_by_upd_document_ids(list(documents_by_id.keys()))
        receipt_logs_by_receipt_id = self.repo.get_warehouse_receipt_logs_by_receipt_ids(
            [
                receipt.id
                for receipts in receipts_by_document_id.values()
                for receipt in receipts
            ]
        )

        history = []
        for row in rows:
            mapping = mappings_by_id.get(row.upd_item_mapping_id)
            document = documents_by_id.get(mapping.upd_documents_id) if mapping and mapping.upd_documents_id else None
            document_item = (
                document_items_by_id.get(mapping.upd_documents_item_id)
                if mapping and mapping.upd_documents_item_id
                else None
            )
            receipts = receipts_by_document_id.get(document.id, []) if document else []
            primary_receipt = receipts[0] if receipts else None
            receipt_logs = [
                log
                for receipt in receipts
                for log in receipt_logs_by_receipt_id.get(receipt.id, [])
            ]
            receipt_logs.sort(key=lambda log: log.id, reverse=True)

            history.append(
                {
                    "id": row.id,
                    "warehouse_list_id": row.id,
                    "upd_item_mapping_id": row.upd_item_mapping_id,
                    "upd_documents_id": mapping.upd_documents_id if mapping else None,
                    "upd_documents_item_id": mapping.upd_documents_item_id if mapping else None,
                    "warehouse_receipt_id": primary_receipt.id if primary_receipt else None,
                    "warehouse_receipt_ids": [receipt.id for receipt in receipts],
                    "warehouse_receipt_log_ids": [log.id for log in receipt_logs],
                    "warehouse_receipt_log_last_id": receipt_logs[0].id if receipt_logs else None,
                    "nomenclature_id": nomenclature.id,
                    "nomenclature_name": nomenclature.name,
                    "unit_id": nomenclature.unit_id,
                    "unit_name": unit.name if unit else None,
                    "upd_item_name": document_item.name if document_item else None,
                    "quantity": row.quantity,
                    "date": row.date,
                    "document_num": document.num if document else None,
                    "document_date": document.date if document else None,
                }
            )

        history.sort(
            key=lambda item: (
                item["warehouse_receipt_log_last_id"] or 0,
                item["date"] or dt_date.min,
                item["warehouse_list_id"],
            ),
            reverse=True,
        )
        return {
            "nomenclature_id": nomenclature.id,
            "nomenclature_name": nomenclature.name,
            "unit_id": nomenclature.unit_id,
            "unit_name": unit.name if unit else None,
            "items": history,
        }

    def get_nomenclature_movement_history(self, nomenclature_id: str):
        nomenclature = self.repo.get_nomenclature_by_id(nomenclature_id)
        if not nomenclature:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nomenclature not found")

        units_by_id = {
            item.id: item
            for item in self.request_repo.get_units_by_ids([nomenclature.unit_id] if nomenclature.unit_id else [])
        }
        unit = units_by_id.get(nomenclature.unit_id) if nomenclature.unit_id else None

        receipt_items = self.repo.get_receipt_items_by_nomenclature(nomenclature_id)
        if not receipt_items:
            return {
                "nomenclature_id": nomenclature.id,
                "nomenclature_name": nomenclature.name,
                "unit_id": nomenclature.unit_id,
                "unit_name": unit.name if unit else None,
                "items": [],
            }

        receipts_by_id = self.repo.get_warehouse_receipts_by_ids(
            [item.warehouse_receipt_id for item in receipt_items if item.warehouse_receipt_id]
        )
        logs_by_item_id = self.repo.get_warehouse_receipt_item_logs_by_item_ids([item.id for item in receipt_items])
        deliveries_by_id = self.repo.get_deliveries_by_ids(
            [receipt.delivery_id for receipt in receipts_by_id.values() if receipt and receipt.delivery_id]
        )
        upd_item_mappings = self.repo.get_upd_item_mappings_by_document_ids_and_nomenclature(
            [receipt.upd_documents_id for receipt in receipts_by_id.values() if receipt and receipt.upd_documents_id],
            nomenclature_id,
        )
        delivery_item_mappings = self.repo.get_delivery_item_mappings_by_delivery_ids_and_nomenclature(
            list(deliveries_by_id.keys()),
            nomenclature_id,
        )
        invoices_by_id = self.repo.get_invoices_by_ids(
            [delivery.invoice_id for delivery in deliveries_by_id.values() if delivery and delivery.invoice_id is not None]
        )
        requests_by_id = self.repo.get_requests_by_ids(
            [
                request_id
                for request_id in (
                    [delivery.request_id for delivery in deliveries_by_id.values() if delivery]
                    + [invoice.request_id for invoice in invoices_by_id.values() if invoice]
                )
                if request_id is not None
            ]
        )
        delivery_items = self.repo.get_delivery_items_by_delivery_ids(list(deliveries_by_id.keys()))
        delivery_items_by_delivery_id: dict[str, list] = {}
        for row in delivery_items:
            delivery_items_by_delivery_id.setdefault(row.delivery_id, []).append(row)
        delivery_items_by_id = {row.id: row for row in delivery_items}
        delivery_item_mappings_by_delivery_id: dict[str, list] = {}
        for row in delivery_item_mappings:
            delivery_item_mappings_by_delivery_id.setdefault(row.delivery_id, []).append(row)
        upd_item_mappings_by_document_id: dict[str, list] = {}
        for row in upd_item_mappings:
            upd_item_mappings_by_document_id.setdefault(row.upd_documents_id, []).append(row)
        invoice_items_by_id = self.repo.get_invoice_items_by_ids(
            [
                item.invoice_item_id
                for item in delivery_items
                if item.invoice_item_id
            ]
        )
        upd_document_items_by_id = self.repo.get_upd_document_items_by_ids(
            [
                item.upd_documents_item_id
                for item in upd_item_mappings
                if item.upd_documents_item_id
            ]
        )

        history = []
        for item in receipt_items:
            receipt = receipts_by_id.get(item.warehouse_receipt_id)
            operation_meta = self._get_receipt_operation_meta(receipt.type if receipt else None)
            delivery = deliveries_by_id.get(receipt.delivery_id) if receipt and receipt.delivery_id else None
            invoice = invoices_by_id.get(delivery.invoice_id) if delivery and delivery.invoice_id is not None else None
            request = (
                requests_by_id.get(delivery.request_id)
                if delivery and delivery.request_id is not None
                else requests_by_id.get(invoice.request_id) if invoice and invoice.request_id is not None else None
            )
            linked_delivery_items = []
            invoice_item_name = None
            upd_item_name = None
            if delivery:
                mapping_rows = delivery_item_mappings_by_delivery_id.get(delivery.id, [])
                for mapping_row in mapping_rows:
                    delivery_item = delivery_items_by_id.get(mapping_row.delivery_item_id)
                    if not delivery_item:
                        continue
                    linked_delivery_items.append(delivery_item)
                    if not invoice_item_name and delivery_item.name:
                        invoice_item_name = delivery_item.name
                if not linked_delivery_items:
                    linked_delivery_items = [
                        delivery_item
                        for delivery_item in delivery_items_by_delivery_id.get(delivery.id, [])
                        if delivery_item.nomenclature_id == nomenclature_id
                    ]
                    if linked_delivery_items and linked_delivery_items[0].name:
                        invoice_item_name = linked_delivery_items[0].name
            if receipt and receipt.upd_documents_id:
                upd_mapping_rows = upd_item_mappings_by_document_id.get(receipt.upd_documents_id, [])
                for upd_mapping_row in upd_mapping_rows:
                    upd_document_item = upd_document_items_by_id.get(upd_mapping_row.upd_documents_item_id)
                    if upd_document_item and upd_document_item.name:
                        upd_item_name = upd_document_item.name
                        break

            # keep item entries for running balance calculation (filtered out later)
            history.append(
                self._build_movement_history_entry(
                    kind="warehouse_receipt_item",
                    event_at=receipt.created_at if receipt else None,
                    nomenclature=nomenclature,
                    unit=unit,
                    receipt_item=item,
                    receipt=receipt,
                    operation_meta=operation_meta,
                    delivery=delivery,
                    invoice=invoice,
                    request=request,
                    delivery_items=linked_delivery_items,
                    invoice_items_by_id=invoice_items_by_id,
                    invoice_item_name=invoice_item_name,
                    upd_item_name=upd_item_name,
                    item_log=None,
                )
            )

            for item_log in logs_by_item_id.get(item.id, []):
                history.append(
                    self._build_movement_history_entry(
                        kind="warehouse_receipt_item_log",
                        event_at=item_log.created_at,
                        nomenclature=nomenclature,
                        unit=unit,
                        receipt_item=item,
                        receipt=receipt,
                        operation_meta=operation_meta,
                        delivery=delivery,
                        invoice=invoice,
                        request=request,
                        delivery_items=linked_delivery_items,
                        invoice_items_by_id=invoice_items_by_id,
                        invoice_item_name=invoice_item_name,
                        upd_item_name=upd_item_name,
                        item_log=item_log,
                    )
                )

        # sort ascending for running balance calculation
        history.sort(
            key=lambda row: (row["event_at"] or dt_datetime.min, row["id"]),
        )

        # compute running total across all receipt items for this nomenclature
        balance = 0.0
        for entry in history:
            entry_qty = entry["quantity"] or 0
            sign = 1 if entry["movement"] and entry["movement"].startswith("+") else -1 if entry["movement"] and entry["movement"].startswith("-") else 0
            entry["quantity_before"] = round(balance, 8)
            balance += sign * entry_qty
            entry["quantity_after"] = round(balance, 8)

        # sort descending for display
        history.sort(
            key=lambda row: (row["event_at"] or dt_datetime.min, row["id"]),
            reverse=True,
        )

        # show only log entries, item entries were needed only for balance calculation
        history = [entry for entry in history if entry["kind"] == "warehouse_receipt_item_log"]

        return {
            "nomenclature_id": nomenclature.id,
            "nomenclature_name": nomenclature.name,
            "unit_id": nomenclature.unit_id,
            "unit_name": unit.name if unit else None,
            "items": history,
        }

    def create_nomenclature(self, payload: NomenclatureCreate, user_id: str):
        data = payload.model_dump(exclude_unset=True)
        data["created_by"] = user_id
        row = self.repo.create_nomenclature(data)
        rows = self._serialize_nomenclature_rows([row])
        return rows[0]

    def update_nomenclature(self, nomenclature_id: str, payload: NomenclatureUpdate):
        row = self.repo.get_nomenclature_by_id(nomenclature_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nomenclature not found")

        data = payload.model_dump(exclude_unset=True)
        updated = self.repo.save_nomenclature(nomenclature_id, data)
        rows = self._serialize_nomenclature_rows([updated])
        return rows[0]

    def delete_nomenclature(self, nomenclature_id: str):
        row = self.repo.get_nomenclature_by_id(nomenclature_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nomenclature not found")
        self.repo.delete_nomenclature(nomenclature_id)
        return None

    def get_price_history(self, nomenclature_id: str, price_type: str | None = None):
        nomenclature = self.repo.get_nomenclature_by_id(nomenclature_id)
        if not nomenclature:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nomenclature not found")
        return [self._serialize_price_history_row(row) for row in self.repo.get_price_history(nomenclature_id, price_type)]

    def create_price_history(self, payload: WarehousePriceHistoryCreate):
        nomenclature = self.repo.get_nomenclature_by_id(payload.nomenclature_id)
        if not nomenclature:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nomenclature not found")
        row = self.repo.create_price_history(payload.model_dump(exclude_unset=True))
        return self._serialize_price_history_row(row)

    @staticmethod
    def _get_receipt_operation_meta(receipt_type: int | None) -> dict:
        mapping = {
            1: {"operation": "приход", "sign": "+"},
            2: {"operation": "расход", "sign": "-"},
            3: {"operation": "возврат", "sign": "+"},
            4: {"operation": "инвентаризация", "sign": ""},
        }
        return mapping.get(receipt_type, {"operation": None, "sign": ""})

    def _build_movement_history_entry(
        self,
        *,
        kind: str,
        event_at,
        nomenclature,
        unit,
        receipt_item,
        receipt,
        operation_meta: dict,
        delivery,
        invoice,
        request,
        delivery_items: list,
        invoice_items_by_id: dict,
        invoice_item_name: str | None,
        upd_item_name: str | None,
        item_log,
    ) -> dict:
        quantity = float(receipt_item.quantity) if receipt_item.quantity is not None else None
        movement_display = None
        if quantity is not None:
            sign = operation_meta.get("sign") or ""
            movement_display = f"{sign}{quantity}"

        return {
            "id": f"{kind}:{item_log.id if item_log else receipt_item.id}",
            "kind": kind,
            "event_at": event_at,
            "movement": movement_display,
            "quantity": quantity,
            "operation": operation_meta.get("operation"),
            "warehouse_receipt_type": receipt.type if receipt else None,
            "warehouse_receipt_id": receipt.id if receipt else receipt_item.warehouse_receipt_id,
            "warehouse_receipt_num": receipt.num if receipt else None,
            "warehouse_receipt_created_at": receipt.created_at if receipt else None,
            "warehouse_receipt_date_arrival": receipt.date_arrival if receipt else None,
            "warehouse_receipt_item_id": receipt_item.id,
            "warehouse_receipt_item_log_id": item_log.id if item_log else None,
            "warehouse_receipt_item_log_created_at": item_log.created_at if item_log else None,
            "upd_documents_id": receipt.upd_documents_id if receipt else None,
            "delivery_id": receipt.delivery_id if receipt else None,
            "nomenclature_id": nomenclature.id,
            "nomenclature_name": nomenclature.name,
            "unit_id": nomenclature.unit_id,
            "unit_name": unit.name if unit else None,
            "receipt_item": {
                "id": receipt_item.id,
                "price": receipt_item.price,
                "price_opt": receipt_item.price_opt,
                "price_opt2": receipt_item.price_opt2,
                "price_retail": receipt_item.price_retail,
                "object_id": receipt_item.object_id,
                "comment": receipt_item.comment,
                "attribute": receipt_item.attribute,
            },
            "delivery": {
                "id": delivery.id,
                "num": delivery.num,
                "request_id": delivery.request_id,
                "invoice_id": delivery.invoice_id,
                "status_id": delivery.status_id,
                "carrier_id": delivery.carrier_id,
                "pick_up_date": delivery.pick_up_date,
                "planned_delivery_from": delivery.planned_delivery_from,
                "planned_delivery_to": delivery.planned_delivery_to,
                "delivery_from": delivery.delivery_from,
                "delivery_to": delivery.delivery_to,
                "comment": delivery.comment,
            } if delivery else None,
            "delivery_items": [
                {
                    "id": delivery_item.id,
                    "name": delivery_item.name,
                    "unit_name": delivery_item.unit_name,
                    "quantity": delivery_item.quantity,
                    "request_item_id": delivery_item.request_item_id,
                    "invoice_item_id": delivery_item.invoice_item_id,
                    "invoice_item": self._serialize_invoice_item(
                        invoice_items_by_id.get(delivery_item.invoice_item_id)
                    ) if delivery_item.invoice_item_id else None,
                }
                for delivery_item in delivery_items
            ],
            "invoice": {
                "id": invoice.id,
                "num": invoice.num,
                "date": invoice.date,
                "request_id": invoice.request_id,
                "provider_id": invoice.provider_id,
                "payer_id": invoice.payer_id,
                "total_amount": invoice.total_amount,
                "vat_rate": invoice.vat_rate,
                "vat_amount": invoice.vat_amount,
                "status": invoice.status,
            } if invoice else None,
            "request": {
                "id": request.id,
                "name": request.name,
                "object_levels_id": request.object_levels_id,
            } if request else None,
            "invoice_item_name": invoice_item_name,
            "upd_item_name": upd_item_name,
        }

    @staticmethod
    def _serialize_invoice_item(invoice_item):
        if not invoice_item:
            return None
        return {
            "id": invoice_item.id,
            "name": invoice_item.name,
            "unit_name": invoice_item.unit_name,
            "quantity": invoice_item.quantity,
            "price": invoice_item.price,
            "sum": invoice_item.sum,
            "nds": invoice_item.nds,
            "value_nds": invoice_item.value_nds,
            "unit_id": invoice_item.unit_id,
            "converted_quantity": invoice_item.converted_quantity,
        }

    def update_price_history(self, row_id: str, payload: WarehousePriceHistoryUpdate):
        row = self.repo.get_price_history_row_by_id(row_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse price history not found")

        data = payload.model_dump(exclude_unset=True)
        nomenclature_id = data.get("nomenclature_id")
        if nomenclature_id:
            nomenclature = self.repo.get_nomenclature_by_id(nomenclature_id)
            if not nomenclature:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nomenclature not found")

        for key, value in data.items():
            setattr(row, key, value)

        updated = self.repo.save_price_history(row)
        return self._serialize_price_history_row(updated)

    def delete_price_history(self, row_id: str):
        row = self.repo.get_price_history_row_by_id(row_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse price history not found")
        self.repo.delete_price_history(row)
        return None

    def _serialize_nomenclature_rows(self, rows):
        unit_ids = [item.unit_id for item in rows if item.unit_id]
        category_ids = [item.warehouse_category_id for item in rows if item.warehouse_category_id]
        units = self.request_repo.get_units_by_ids(unit_ids)
        categories = self.request_repo.get_warehouse_categories_by_ids(category_ids)
        units_by_id = {item.id: item for item in units}
        categories_by_id = {item.id: item for item in categories}

        result = []
        for item in rows:
            unit = units_by_id.get(item.unit_id)
            category = categories_by_id.get(item.warehouse_category_id)
            result.append(
                {
                    "id": item.id,
                    "name": item.name,
                    "description": item.description,
                    "article": item.article,
                    "unit_id": item.unit_id,
                    "warehouse_category_id": item.warehouse_category_id,
                    "unit": None if not unit else {"id": unit.id, "name": unit.name},
                    "warehouse_category": None
                    if not category
                    else {
                        "id": category.id,
                        "name": category.name,
                        "parent_id": category.parent_id,
                    },
                    "length": item.length,
                    "width": item.width,
                    "height": item.height,
                    "weight": item.weight,
                    "vat_rate": item.vat_rate,
                    "price_opt": item.price_opt,
                    "price_opt2": item.price_opt2,
                    "price_retail": item.price_retail,
                    "created_at": item.created_at,
                    "created_by": item.created_by,
                }
            )

        return result

    @staticmethod
    def _serialize_price_history_row(row):
        return {
            "id": row.id,
            "nomenclature_id": row.nomenclature_id,
            "type": row.type,
            "value": row.value,
            "date": row.date,
        }
