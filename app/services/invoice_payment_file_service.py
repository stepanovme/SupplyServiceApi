from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import HTTPException, status

from app.models.invoice_payment_file import InvoicePaymentFileCreate, InvoicePaymentFileUpdate
from app.repositories.invoice_payment_file_repository import InvoicePaymentFileRepository

BASE_PAYMENT_FILES_DIR = "/home/webserver/models/supply/invoices/payments"


class InvoicePaymentFileService:
    def __init__(self, repo: InvoicePaymentFileRepository) -> None:
        self.repo = repo

    def get_by_payment_id(self, payment_id: str):
        return [self._serialize(row) for row in self.repo.get_by_payment_id(payment_id)]

    def get_by_id(self, row_id: str):
        row = self.repo.get_by_id(row_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment file not found")
        return self._serialize(row)

    def upload(self, payment_id: str, original_name: str, file_bytes: bytes, user_id: str):
        extension = Path(original_name).suffix.lower().lstrip(".")
        storage_name = f"{uuid.uuid4().hex}{('.' + extension) if extension else ''}"
        target_dir = os.path.join(BASE_PAYMENT_FILES_DIR, payment_id)
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, storage_name)

        with open(file_path, "wb") as file_stream:
            file_stream.write(file_bytes)

        created = self.repo.create(
            payment_id,
            {
                "original_name": original_name,
                "storage_name": storage_name,
                "file_path": file_path,
                "uploaded_by": user_id,
            },
        )
        return self._serialize(created)

    def update(self, row_id: str, payload: InvoicePaymentFileUpdate):
        row = self.repo.get_by_id(row_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment file not found")
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save(row)
        return self._serialize(updated)

    def delete(self, row_id: str):
        row = self.repo.get_by_id(row_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment file not found")
        if row.file_path and os.path.exists(row.file_path):
            os.remove(row.file_path)
        self.repo.delete(row)
        return None

    def get_download(self, row_id: str) -> tuple[str, str]:
        row = self.repo.get_by_id(row_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment file not found")
        if not row.file_path or not os.path.exists(row.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment file not found on disk")
        return row.file_path, row.original_name

    @staticmethod
    def _serialize(row) -> dict:
        return {
            "id": row.id,
            "invoice_payment_id": row.invoice_payment_id,
            "original_name": row.original_name,
            "storage_name": row.storage_name,
            "file_path": row.file_path,
            "uploaded_by": row.uploaded_by,
            "uploaded_at": row.uploaded_at,
        }
