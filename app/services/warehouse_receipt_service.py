from collections import defaultdict

from fastapi import HTTPException, status

from app.models.warehouse_receipt import (
    WarehouseReceiptCreate,
    WarehouseReceiptItemCreate,
    WarehouseReceiptItemUpdate,
    WarehouseReceiptUpdate,
)
from app.repositories.counterparty_repository import CounterpartyRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.repositories.warehouse_receipt_repository import WarehouseReceiptRepository

DEFAULT_WAREHOUSE_RECEIPT_STATUS_ID = "ff28c5a3-1968-11f1-aa8c-bc241127d0bd"


class WarehouseReceiptService:
    def __init__(
        self,
        repo: WarehouseReceiptRepository,
        counterparty_repo: CounterpartyRepository,
        reference_repo: ReferenceObjectRepository,
    ) -> None:
        self.repo = repo
        self.counterparty_repo = counterparty_repo
        self.reference_repo = reference_repo

    def get_receipts(self):
        receipts = self.repo.get_receipts()
        return self._serialize_receipts(receipts)

    def get_receipt(self, receipt_id: str):
        receipt = self.repo.get_receipt_by_id(receipt_id)
        if not receipt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Warehouse receipt not found",
            )
        return self._serialize_receipts([receipt])[0]

    def create_receipt(self, payload: WarehouseReceiptCreate):
        data = payload.model_dump(exclude_unset=True, by_alias=False)
        if not data.get("warehouse_id"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="warehouse_id is required",
            )
        if data.get("num") is None:
            data["num"] = self.repo.get_next_receipt_num()
        data.setdefault("status_id", DEFAULT_WAREHOUSE_RECEIPT_STATUS_ID)

        row = self.repo.create_receipt(data)
        return self.get_receipt(row.id)

    def update_receipt(self, receipt_id: str, payload: WarehouseReceiptUpdate):
        row = self.repo.get_receipt_by_id(receipt_id)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Warehouse receipt not found",
            )

        data = payload.model_dump(exclude_unset=True, by_alias=False)
        for key, value in data.items():
            setattr(row, key, value)

        updated = self.repo.save_receipt(row)
        return self.get_receipt(updated.id)

    def delete_receipt(self, receipt_id: str):
        row = self.repo.get_receipt_by_id(receipt_id)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Warehouse receipt not found",
            )
        self.repo.delete_receipt(row)
        return None

    def get_receipt_items(self, receipt_id: str):
        if not self.repo.get_receipt_by_id(receipt_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Warehouse receipt not found",
            )
        items = self.repo.get_receipt_items(receipt_id)
        return self._serialize_items(items)

    def create_receipt_item(self, receipt_id: str, payload: WarehouseReceiptItemCreate):
        if not self.repo.get_receipt_by_id(receipt_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Warehouse receipt not found",
            )

        data = payload.model_dump(exclude_unset=True)
        if data.get("price") is None:
            data["price"] = 0
        item = self.repo.create_receipt_item(receipt_id, data)
        return self._serialize_items([item])[0]

    def update_receipt_item(
        self,
        receipt_id: str,
        item_id: str,
        payload: WarehouseReceiptItemUpdate,
    ):
        item = self.repo.get_receipt_item_by_id(receipt_id, item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Warehouse receipt item not found",
            )

        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(item, key, value)

        updated = self.repo.save_receipt_item(item)
        return self._serialize_items([updated])[0]

    def delete_receipt_item(self, receipt_id: str, item_id: str):
        item = self.repo.get_receipt_item_by_id(receipt_id, item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Warehouse receipt item not found",
            )
        self.repo.delete_receipt_item(item)
        return None

    def _serialize_receipts(self, receipts):
        receipt_ids = [receipt.id for receipt in receipts]
        items = self.repo.get_receipt_items_by_receipt_ids(receipt_ids)
        items_by_receipt_id = defaultdict(list)
        for item in items:
            items_by_receipt_id[item.warehouse_receipt_id].append(item)

        status_ids = [receipt.status_id for receipt in receipts if receipt.status_id]
        warehouse_ids = [receipt.warehouse_id for receipt in receipts if receipt.warehouse_id]
        from_ids = [receipt.from_id for receipt in receipts if receipt.from_id]
        object_ids = [receipt.object_id for receipt in receipts if receipt.object_id]

        for item in items:
            if item.object_id:
                object_ids.append(item.object_id)

        status_names = self.repo.get_status_names(status_ids)
        warehouses = self.repo.get_warehouses(warehouse_ids)
        counterparties = self.reference_repo.get_counterparty_names(from_ids)
        object_rows = self.reference_repo.get_objects_by_ids(object_ids)
        object_names = {row.id: (row.short_name or row.full_name) for row in object_rows}

        result = []
        for receipt in receipts:
            receipt_items = self._serialize_items(
                items_by_receipt_id.get(receipt.id, []),
                object_names,
            )
            result.append(
                {
                    "id": receipt.id,
                    "num": receipt.num,
                    "from": receipt.from_id,
                    "from_name": counterparties.get(receipt.from_id),
                    "object_id": receipt.object_id,
                    "object_name": object_names.get(receipt.object_id),
                    "file_id": receipt.file_id,
                    "created_at": receipt.created_at,
                    "date_arrival": receipt.date_arrival,
                    "date_completed": receipt.date_completed,
                    "warehouse_id": receipt.warehouse_id,
                    "warehouse_name": warehouses.get(receipt.warehouse_id).name
                    if warehouses.get(receipt.warehouse_id)
                    else None,
                    "delivery_id": receipt.delivery_id,
                    "status_id": receipt.status_id,
                    "status_name": status_names.get(receipt.status_id),
                    "items": receipt_items,
                }
            )

        return result

    def _serialize_items(self, items, object_names: dict[str, str] | None = None):
        object_names = object_names or {}
        nomenclature_ids = [item.nomenclature_id for item in items if item.nomenclature_id]
        nomenclature = self.repo.get_nomenclature(nomenclature_ids)

        if not object_names:
            object_rows = self.reference_repo.get_objects_by_ids(
                [item.object_id for item in items if item.object_id]
            )
            object_names = {row.id: (row.short_name or row.full_name) for row in object_rows}

        result = []
        for item in items:
            nom = nomenclature.get(item.nomenclature_id)
            result.append(
                {
                    "id": item.id,
                    "warehouse_receipt_id": item.warehouse_receipt_id,
                    "nomenclature_id": item.nomenclature_id,
                    "nomenclature_name": nom.name if nom else None,
                    "quantity": item.quantity,
                    "price": item.price,
                    "object_id": item.object_id,
                    "object_name": object_names.get(item.object_id),
                }
            )
        return result
