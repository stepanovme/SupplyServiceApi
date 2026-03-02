import hashlib
import os
import uuid
from pathlib import Path

from fastapi import HTTPException, status

from app.models.request_file import FileAudit, FileDB
from app.models.invoice import (
    InvoiceCreate,
    InvoiceItemCreate,
    InvoiceItemUpdate,
    InvoiceUpdate,
)
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.request_file_repository import RequestFileRepository

DEFAULT_NEW_STATUS_ID = "1ff34436-1312-11f1-aa8c-bc241127d0bd"
INVOICE_FILE_TYPE_ID = "4594a94b-140f-11f1-aa8c-bc241127d0bd"
BASE_INVOICE_FILES_DIR = os.getenv(
    "SUPPLY_INVOICE_FILES_DIR",
    "/home/webserver/models/supply/invoices",
)


class InvoiceService:
    def __init__(
        self,
        repo: InvoiceRepository,
        file_repo: RequestFileRepository | None = None,
    ) -> None:
        self.repo = repo
        self.file_repo = file_repo

    def create_invoice(self, payload: InvoiceCreate, user_id: str):
        data = payload.model_dump(exclude_unset=True)
        data.setdefault("is_delivery_included", False)
        data.setdefault("prepayment_percent", 0)
        data.setdefault("due_days", 0)
        data.setdefault("valid_until", 0)
        data.setdefault("is_urgent", False)
        data.setdefault("total_amount", 0)
        data.setdefault("vat_rate", 0)
        data.setdefault("vat_amount", 0)
        data.setdefault("status", DEFAULT_NEW_STATUS_ID)
        data["created_by"] = user_id

        created = self.repo.create_invoice(data)
        return self.get_invoice(created.id)

    def create_invoice_with_file(
        self,
        payload: InvoiceCreate,
        user_id: str,
        original_name: str,
        mime_type: str,
        file_bytes: bytes,
    ):
        if not self.file_repo:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="File repository is not configured",
            )

        file_type = self.file_repo.get_file_type_by_id(INVOICE_FILE_TYPE_ID)
        if not file_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Active invoice file type not found",
            )

        extension = Path(original_name).suffix.lower().lstrip(".")
        if not extension:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File extension is required",
            )

        allowed_extensions = file_type.allowed_extensions or []
        if isinstance(allowed_extensions, str):
            allowed_extensions = [allowed_extensions]
        normalized_allowed = [str(item).lower().lstrip(".") for item in allowed_extensions]
        if normalized_allowed and extension not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File extension .{extension} is not allowed",
            )

        max_size_mb = file_type.max_size_mb or 10
        if len(file_bytes) > max_size_mb * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size exceeds {max_size_mb} MB",
            )

        file_id = str(uuid.uuid4())
        storage_name = f"{uuid.uuid4().hex}.{extension}"
        directory_suffix = str(payload.request_id) if payload.request_id is not None else user_id
        invoice_dir = os.path.join(BASE_INVOICE_FILES_DIR, directory_suffix)
        self._ensure_directory(invoice_dir)

        file_path = os.path.join(invoice_dir, storage_name)
        with open(file_path, "wb") as file_stream:
            file_stream.write(file_bytes)

        md5_hash = hashlib.md5(file_bytes).hexdigest()
        file_row = FileDB(
            id=file_id,
            original_name=original_name,
            storage_name=storage_name,
            file_type_id=file_type.id,
            mime_type=mime_type or "application/octet-stream",
            extension=extension,
            file_size=len(file_bytes),
            md5_hash=md5_hash,
            file_path=file_path,
            version=1,
            uploaded_by=user_id,
            status="active",
        )

        try:
            created_file = self.file_repo.create_file(file_row)
            self.file_repo.add_audit(
                FileAudit(
                    id=str(uuid.uuid4()),
                    file_id=created_file.id,
                    action="upload",
                    user_id=user_id,
                )
            )
        except Exception:
            if os.path.exists(file_path):
                os.remove(file_path)
            raise

        data = payload.model_dump(exclude_unset=True)
        data["file_id"] = created_file.id
        data.setdefault("is_delivery_included", False)
        data.setdefault("prepayment_percent", 0)
        data.setdefault("due_days", 0)
        data.setdefault("valid_until", 0)
        data.setdefault("is_urgent", False)
        data.setdefault("total_amount", 0)
        data.setdefault("vat_rate", 0)
        data.setdefault("vat_amount", 0)
        data.setdefault("status", DEFAULT_NEW_STATUS_ID)
        data["created_by"] = user_id

        created = self.repo.create_invoice(data)
        return self.get_invoice(created.id)

    @staticmethod
    def _ensure_directory(path: str) -> None:
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    f"Cannot create directory '{path}'. "
                    "Set SUPPLY_INVOICE_FILES_DIR to a writable path."
                ),
            ) from exc

    def update_invoice(self, invoice_id: int, payload: InvoiceUpdate):
        invoice = self.repo.get_invoice_by_id(invoice_id)
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(invoice, key, value)

        updated = self.repo.save_invoice(invoice)
        return self.get_invoice(updated.id)

    def delete_invoice(self, invoice_id: int):
        invoice = self.repo.get_invoice_by_id(invoice_id)
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

        self.repo.delete_invoice(invoice)
        return None

    def create_invoice_item(self, invoice_id: int, payload: InvoiceItemCreate):
        invoice = self.repo.get_invoice_by_id(invoice_id)
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

        data = payload.model_dump(exclude_unset=True)
        item = self.repo.create_invoice_item(invoice_id, data)
        return self._item_to_dict(item)

    def update_invoice_item(self, invoice_id: int, item_id: str, payload: InvoiceItemUpdate):
        item = self.repo.get_invoice_item_by_id(invoice_id, item_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice item not found")

        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(item, key, value)

        updated = self.repo.save_invoice_item(item)
        return self._item_to_dict(updated)

    def delete_invoice_item(self, invoice_id: int, item_id: str):
        item = self.repo.get_invoice_item_by_id(invoice_id, item_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice item not found")

        self.repo.delete_invoice_item(item)
        return None

    def get_invoice(self, invoice_id: int):
        invoice = self.repo.get_invoice_by_id(invoice_id)
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

        items = self.repo.get_invoice_items(invoice_id)
        return {
            "id": invoice.id,
            "request_id": invoice.request_id,
            "file_id": invoice.file_id,
            "provider_id": invoice.provider_id,
            "payer_id": invoice.payer_id,
            "is_delivery_included": invoice.is_delivery_included,
            "prepayment_percent": invoice.prepayment_percent,
            "due_days": invoice.due_days,
            "valid_until": invoice.valid_until,
            "is_urgent": invoice.is_urgent,
            "total_amount": invoice.total_amount,
            "vat_rate": invoice.vat_rate,
            "vat_amount": invoice.vat_amount,
            "status": invoice.status,
            "created_at": invoice.created_at,
            "updated_at": invoice.updated_at,
            "created_by": invoice.created_by,
            "items": [self._item_to_dict(item) for item in items],
        }

    @staticmethod
    def _item_to_dict(item):
        return {
            "id": item.id,
            "invoice_id": item.invoice_id,
            "name": item.name,
            "unit_name": item.unit_name,
            "quantity": item.quantity,
            "price": item.price,
            "sum": item.sum,
            "nds": item.nds,
            "value_nds": item.value_nds,
            "unit_id": item.unit_id,
            "converted_quantity": item.converted_quantity,
        }
