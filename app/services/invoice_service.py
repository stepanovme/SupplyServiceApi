from fastapi import HTTPException, status

from app.models.invoice import (
    InvoiceCreate,
    InvoiceItemCreate,
    InvoiceItemUpdate,
    InvoiceUpdate,
)
from app.repositories.invoice_repository import InvoiceRepository

DEFAULT_NEW_STATUS_ID = "1ff34436-1312-11f1-aa8c-bc241127d0bd"


class InvoiceService:
    def __init__(self, repo: InvoiceRepository) -> None:
        self.repo = repo

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
