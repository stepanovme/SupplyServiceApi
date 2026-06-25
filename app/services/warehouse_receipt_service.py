import hashlib
import os
import uuid
from collections import defaultdict
from pathlib import Path

from fastapi import HTTPException, status

from app.models.request_file import FileAudit, FileDB
from app.models.warehouse_receipt import WarehouseFile
from app.models.warehouse_receipt import (
    WarehouseReceiptCreate,
    WarehouseReceiptItemCreate,
    WarehouseReceiptItemLogCreate,
    WarehouseReceiptItemLogUpdate,
    WarehouseReceiptItemUpdate,
    WarehouseReceiptLogCreate,
    WarehouseReceiptLogUpdate,
    WarehouseReceiptUpdate,
)
from app.repositories.counterparty_repository import CounterpartyRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.repositories.warehouse_receipt_repository import WarehouseReceiptRepository

DEFAULT_WAREHOUSE_RECEIPT_STATUS_ID = "ff28c5a3-1968-11f1-aa8c-bc241127d0bd"
BASE_WAREHOUSE_RECEIPT_FILES_DIR = os.getenv(
    "SUPPLY_WAREHOUSE_RECEIPT_FILES_DIR",
    "/home/webserver/models/supply/warehouse",
)
WAREHOUSE_RECEIPT_ATTACHMENT_FILE_TYPE_CODE = "request_attachment"


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

    def get_receipts(self, warehouse_id: str | None = None):
        receipts = self.repo.get_receipts_by_type(1, warehouse_id)
        return self._serialize_receipts(receipts)

    def get_outgoing_receipts(self):
        receipts = self.repo.get_receipts_by_type(2)
        return self._serialize_receipts(receipts)

    def get_return_receipts(self):
        receipts = self.repo.get_receipts_by_type(3)
        return self._serialize_receipts(receipts)

    def get_inventory_receipts(self):
        receipts = self.repo.get_receipts_by_type(4)
        return self._serialize_receipts(receipts)

    def get_unique_receipt_parties(self):
        return [{"value": value} for value in self.repo.get_unique_receipt_parties()]

    def get_receipt(self, receipt_id: str):
        receipt = self.repo.get_receipt_by_id(receipt_id)
        if not receipt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Warehouse receipt not found",
            )
        return self._serialize_receipts([receipt])[0]

    def create_receipt(self, payload: WarehouseReceiptCreate):
        return self._create_receipt(payload, receipt_type=1)

    def create_outgoing_receipt(self, payload: WarehouseReceiptCreate):
        return self._create_receipt(payload, receipt_type=2)

    def create_return_receipt(self, payload: WarehouseReceiptCreate):
        return self._create_receipt(payload, receipt_type=3)

    def create_inventory_receipt(self, payload: WarehouseReceiptCreate):
        return self._create_receipt(payload, receipt_type=4)

    def _create_receipt(self, payload: WarehouseReceiptCreate, receipt_type: int):
        data = self._normalize_receipt_payload(payload.model_dump(exclude_unset=True, by_alias=False))
        if not data.get("warehouse_id"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="warehouse_id is required",
            )
        if data.get("num") is None:
            data["num"] = self.repo.get_next_receipt_num()
        data.setdefault("status_id", DEFAULT_WAREHOUSE_RECEIPT_STATUS_ID)
        data["type"] = receipt_type

        row = self.repo.create_receipt(data)
        return self.get_receipt(row.id)

    def update_receipt(self, receipt_id: str, payload: WarehouseReceiptUpdate):
        row = self.repo.get_receipt_by_id(receipt_id)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Warehouse receipt not found",
            )

        data = self._normalize_receipt_payload(payload.model_dump(exclude_unset=True, by_alias=False))
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
        receipt = self.repo.get_receipt_by_id(receipt_id)
        if not receipt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Warehouse receipt not found",
            )

        data = payload.model_dump(exclude_unset=True)
        data = self._normalize_receipt_item_payload(data)
        inventory_snapshot = None
        if receipt.type == 4 and data.get("nomenclature_id"):
            inventory_snapshot = self.repo.get_inventory_snapshot(
                nomenclature_id=data["nomenclature_id"],
                warehouse_id=receipt.warehouse_id,
            )
            if data.get("quantity") is None:
                data["quantity"] = inventory_snapshot["total_quantity"]
            if data.get("price") is None and inventory_snapshot["last_price"] is not None:
                data["price"] = inventory_snapshot["last_price"]

        if data.get("price") is None:
            data["price"] = 0
        item = self.repo.create_receipt_item(receipt_id, data)
        payload_item = self._serialize_items([item])[0]
        if inventory_snapshot is not None:
            payload_item["inventory_total_quantity"] = inventory_snapshot["total_quantity"]
            payload_item["inventory_last_price"] = inventory_snapshot["last_price"]
        return payload_item

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

        data = self._normalize_receipt_item_payload(payload.model_dump(exclude_unset=True))
        for key, value in data.items():
            setattr(item, key, value)

        updated = self.repo.save_receipt_item(item)
        return self._serialize_items([updated])[0]

    @staticmethod
    def _normalize_receipt_item_payload(data: dict) -> dict:
        normalized = dict(data)
        # Empty string in nullable FK columns breaks FK checks in MySQL.
        for field_name in ("object_id", "upd_item_mapping"):
            if normalized.get(field_name) == "":
                normalized[field_name] = None
        return normalized

    def delete_receipt_item(self, receipt_id: str, item_id: str):
        item = self.repo.get_receipt_item_by_id(receipt_id, item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Warehouse receipt item not found",
            )
        self.repo.delete_receipt_item(item)
        return None

    def get_receipt_files(self, receipt_id: str):
        if not self.repo.get_receipt_by_id(receipt_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Warehouse receipt not found",
            )

        rows = self.repo.get_warehouse_files(receipt_id)
        return [
            {
                "id": file_row.id,
                "warehouse_file_id": warehouse_file.id,
                "warehouse_receipt_id": warehouse_file.warehouse_receipt_id,
                "created_at": warehouse_file.created_at,
                "original_name": file_row.original_name,
                "mime_type": file_row.mime_type,
                "extension": file_row.extension,
                "file_size": file_row.file_size,
                "uploaded_by": file_row.uploaded_by,
                "uploaded_at": file_row.uploaded_at,
                "file_type": {
                    "id": file_type.id,
                    "code": file_type.code,
                    "name": file_type.name,
                },
                "download_url": f"/api/supply/warehouse-receipts/{receipt_id}/attachments/{file_row.id}/download",
            }
            for warehouse_file, file_row, file_type in rows
        ]

    def upload_receipt_attachment(
        self,
        receipt_id: str,
        original_name: str,
        mime_type: str,
        file_bytes: bytes,
        user_id: str,
    ):
        if not self.repo.get_receipt_by_id(receipt_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Warehouse receipt not found",
            )

        attachment_type = self.repo.get_file_type_by_code(WAREHOUSE_RECEIPT_ATTACHMENT_FILE_TYPE_CODE)
        if not attachment_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Active file type 'request_attachment' not found",
            )

        extension = Path(original_name).suffix.lower().lstrip(".")
        if not extension:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File extension is required",
            )

        allowed_extensions = attachment_type.allowed_extensions or []
        if isinstance(allowed_extensions, str):
            allowed_extensions = [allowed_extensions]
        normalized_allowed = [str(item).lower().lstrip(".") for item in allowed_extensions]
        if normalized_allowed and extension not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File extension .{extension} is not allowed",
            )

        max_size_mb = attachment_type.max_size_mb or 10
        if len(file_bytes) > max_size_mb * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size exceeds {max_size_mb} MB",
            )

        file_id = str(uuid.uuid4())
        storage_name = f"{uuid.uuid4().hex}.{extension}"
        receipt_dir = os.path.join(BASE_WAREHOUSE_RECEIPT_FILES_DIR, receipt_id)
        self._ensure_directory(receipt_dir)
        file_path = os.path.join(receipt_dir, storage_name)

        with open(file_path, "wb") as file_stream:
            file_stream.write(file_bytes)

        file_row = FileDB(
            id=file_id,
            original_name=original_name,
            storage_name=storage_name,
            file_type_id=attachment_type.id,
            mime_type=mime_type or "application/octet-stream",
            extension=extension,
            file_size=len(file_bytes),
            md5_hash=hashlib.md5(file_bytes).hexdigest(),
            file_path=file_path,
            version=1,
            uploaded_by=user_id,
            status="active",
        )
        warehouse_file_row = WarehouseFile(
            id=str(uuid.uuid4()),
            warehouse_receipt_id=receipt_id,
            file_id=file_id,
        )

        try:
            created = self.repo.create_file_and_warehouse_link(file_row, warehouse_file_row)
            self.repo.add_audit(
                FileAudit(
                    id=str(uuid.uuid4()),
                    file_id=file_id,
                    action="upload",
                    user_id=user_id,
                )
            )
        except Exception:
            if os.path.exists(file_path):
                os.remove(file_path)
            raise

        return {
            "id": created.id,
            "warehouse_receipt_id": receipt_id,
            "original_name": created.original_name,
            "mime_type": created.mime_type,
            "extension": created.extension,
            "file_size": created.file_size,
            "file_path": created.file_path,
        }

    def get_download_file_payload(self, receipt_id: str, file_id: str, user_id: str):
        if not self.repo.get_receipt_by_id(receipt_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Warehouse receipt not found",
            )

        row = self.repo.get_warehouse_file(receipt_id, file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

        _, file_row, _ = row
        if not os.path.exists(file_row.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")

        self.repo.add_audit(
            FileAudit(
                id=str(uuid.uuid4()),
                file_id=file_row.id,
                action="download",
                user_id=user_id,
            )
        )

        return {
            "path": file_row.file_path,
            "filename": file_row.original_name,
            "media_type": file_row.mime_type,
        }

    def delete_receipt_file(self, receipt_id: str, file_id: str, user_id: str):
        if not self.repo.get_receipt_by_id(receipt_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Warehouse receipt not found",
            )

        row = self.repo.get_warehouse_file(receipt_id, file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

        _, file_row, _ = row
        self.repo.mark_file_deleted(file_row)
        self.repo.add_audit(
            FileAudit(
                id=str(uuid.uuid4()),
                file_id=file_row.id,
                action="delete",
                user_id=user_id,
            )
        )

        if os.path.exists(file_row.file_path):
            os.remove(file_row.file_path)

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
        to_ids = [receipt.to_id for receipt in receipts if receipt.to_id]
        who_write_off_ids = [receipt.who_write_off for receipt in receipts if receipt.who_write_off]
        toll_company_ids = [receipt.toll_company_id for receipt in receipts if receipt.toll_company_id]
        object_ids = [receipt.object_id for receipt in receipts if receipt.object_id]

        for item in items:
            if item.object_id:
                object_ids.append(item.object_id)

        status_names = self.repo.get_status_names(status_ids)
        warehouses = self.repo.get_warehouses(warehouse_ids)
        counterparty_names = self.reference_repo.get_counterparty_names(from_ids + to_ids + who_write_off_ids + toll_company_ids)
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
                    "type": receipt.type,
                    "from": receipt.from_id,
                    "from_name": counterparty_names.get(receipt.from_id),
                    "to": receipt.to_id,
                    "to_name": counterparty_names.get(receipt.to_id),
                    "area_name": receipt.area_name,
                    "document": receipt.document,
                    "who_write_off": receipt.who_write_off,
                    "who_write_off_name": counterparty_names.get(receipt.who_write_off),
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
                    "toll": receipt.toll,
                    "toll_company_id": receipt.toll_company_id,
                    "toll_company_name": counterparty_names.get(receipt.toll_company_id),
                    "upd_documents_id": receipt.upd_documents_id,
                    "retail": receipt.retail,
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
        units = self.repo.get_units([item.unit_id for item in nomenclature.values() if item.unit_id])

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
                    "unit_id": nom.unit_id if nom else None,
                    "unit_name": units.get(nom.unit_id).name if nom and nom.unit_id and units.get(nom.unit_id) else None,
                    "quantity": item.quantity,
                    "price": item.price,
                    "price_opt": item.price_opt,
                    "price_opt2": item.price_opt2,
                    "price_retail": item.price_retail,
                    "upd_item_mapping": item.upd_item_mapping,
                    "object_id": item.object_id,
                    "object_name": object_names.get(item.object_id),
                    "comment": item.comment,
                    "attribute": item.attribute,
                }
            )
        return result

    def get_receipt_logs(self, receipt_id: str):
        if not self.repo.get_receipt_by_id(receipt_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse receipt not found")
        rows = self.repo.get_receipt_logs(receipt_id)
        warehouses = self.repo.get_warehouses([row.warehouse_id for row in rows if row.warehouse_id])
        return [self._serialize_receipt_log(row, warehouses) for row in rows]

    def create_receipt_log(self, receipt_id: str, payload: WarehouseReceiptLogCreate, user_id: str):
        if not self.repo.get_receipt_by_id(receipt_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse receipt not found")
        data = payload.model_dump(exclude_unset=True)
        data["created_by"] = user_id
        created = self.repo.create_receipt_log(receipt_id, data)
        warehouses = self.repo.get_warehouses([created.warehouse_id] if created.warehouse_id else [])
        return self._serialize_receipt_log(created, warehouses)

    def update_receipt_log(self, receipt_id: str, log_id: int, payload: WarehouseReceiptLogUpdate):
        row = self.repo.get_receipt_log_by_id(receipt_id, log_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse receipt log not found")
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save_receipt_log(row)
        warehouses = self.repo.get_warehouses([updated.warehouse_id] if updated.warehouse_id else [])
        return self._serialize_receipt_log(updated, warehouses)

    def delete_receipt_log(self, receipt_id: str, log_id: int):
        row = self.repo.get_receipt_log_by_id(receipt_id, log_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse receipt log not found")
        self.repo.delete_receipt_log(row)
        return None

    def get_receipt_item_logs(self, receipt_id: str, item_id: str):
        if not self.repo.get_receipt_item_by_id(receipt_id, item_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse receipt item not found")
        rows = self.repo.get_receipt_item_logs(item_id)
        warehouses = self.repo.get_warehouses([row.warehouse_id for row in rows if row.warehouse_id])
        return [self._serialize_receipt_item_log(row, warehouses) for row in rows]

    def create_receipt_item_log(
        self,
        receipt_id: str,
        item_id: str,
        payload: WarehouseReceiptItemLogCreate,
        user_id: str,
    ):
        if not self.repo.get_receipt_item_by_id(receipt_id, item_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse receipt item not found")
        data = payload.model_dump(exclude_unset=True)
        data["created_by"] = user_id
        created = self.repo.create_receipt_item_log(item_id, data)
        warehouses = self.repo.get_warehouses([created.warehouse_id] if created.warehouse_id else [])
        return self._serialize_receipt_item_log(created, warehouses)

    def update_receipt_item_log(
        self,
        receipt_id: str,
        item_id: str,
        log_id: int,
        payload: WarehouseReceiptItemLogUpdate,
    ):
        if not self.repo.get_receipt_item_by_id(receipt_id, item_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse receipt item not found")
        row = self.repo.get_receipt_item_log_by_id(item_id, log_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse receipt item log not found")
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save_receipt_item_log(row)
        warehouses = self.repo.get_warehouses([updated.warehouse_id] if updated.warehouse_id else [])
        return self._serialize_receipt_item_log(updated, warehouses)

    def delete_receipt_item_log(self, receipt_id: str, item_id: str, log_id: int):
        if not self.repo.get_receipt_item_by_id(receipt_id, item_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse receipt item not found")
        row = self.repo.get_receipt_item_log_by_id(item_id, log_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse receipt item log not found")
        self.repo.delete_receipt_item_log(row)
        return None

    @staticmethod
    def _serialize_receipt_log(row, warehouses):
        return {
            "id": row.id,
            "warehouse_receipt_id": row.warehouse_receipt_id,
            "warehouse_id": row.warehouse_id,
            "warehouse_name": warehouses.get(row.warehouse_id).name if warehouses.get(row.warehouse_id) else None,
            "created_at": row.created_at,
            "created_by": row.created_by,
        }

    @staticmethod
    def _serialize_receipt_item_log(row, warehouses):
        return {
            "id": row.id,
            "warehouse_receipt_item_id": row.warehouse_receipt_item_id,
            "warehouse_id": row.warehouse_id,
            "warehouse_name": warehouses.get(row.warehouse_id).name if warehouses.get(row.warehouse_id) else None,
            "created_at": row.created_at,
            "created_by": row.created_by,
        }

    @staticmethod
    def _normalize_receipt_payload(data: dict) -> dict:
        normalized = dict(data)
        for field_name in ("from_id", "to_id", "who_write_off", "object_id", "file_id", "delivery_id", "toll_company_id", "upd_documents_id"):
            if normalized.get(field_name) == "":
                normalized[field_name] = None
        if "toll" in normalized and normalized["toll"] is None:
            normalized["toll"] = False
        return normalized

    @staticmethod
    def _ensure_directory(path: str) -> None:
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    f"Cannot create directory '{path}'. "
                    "Set SUPPLY_WAREHOUSE_RECEIPT_FILES_DIR to a writable path."
                ),
            ) from exc
