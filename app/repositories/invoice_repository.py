import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceItem
from app.models.supply_request import StatusRef, UnitRef


class InvoiceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_invoice(self, payload: dict) -> Invoice:
        row = Invoice(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_invoice_by_id(self, invoice_id: int) -> Invoice | None:
        return self.db.query(Invoice).filter(Invoice.id == invoice_id).first()

    def save_invoice(self, row: Invoice) -> Invoice:
        row.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_invoice(self, row: Invoice) -> None:
        self.db.delete(row)
        self.db.commit()

    def get_invoice_items(self, invoice_id: int) -> list[InvoiceItem]:
        return (
            self.db.query(InvoiceItem)
            .filter(InvoiceItem.invoice_id == invoice_id)
            .all()
        )

    def create_invoice_item(self, invoice_id: int, payload: dict) -> InvoiceItem:
        item = InvoiceItem(id=str(uuid.uuid4()), invoice_id=invoice_id, **payload)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_invoice_item_by_id(self, invoice_id: int, item_id: str) -> InvoiceItem | None:
        return (
            self.db.query(InvoiceItem)
            .filter(
                InvoiceItem.invoice_id == invoice_id,
                InvoiceItem.id == item_id,
            )
            .first()
        )

    def save_invoice_item(self, item: InvoiceItem) -> InvoiceItem:
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete_invoice_item(self, item: InvoiceItem) -> None:
        self.db.delete(item)
        self.db.commit()

    def get_status_name(self, status_id: str | None) -> str | None:
        if not status_id:
            return None
        row = self.db.query(StatusRef).filter(StatusRef.id == status_id).first()
        return row.name if row else None

    def get_unit_names(self, unit_ids: list[str]) -> dict[str, str]:
        if not unit_ids:
            return {}

        rows = (
            self.db.query(UnitRef.id, UnitRef.name)
            .filter(UnitRef.id.in_(unit_ids))
            .all()
        )
        return {str(unit_id): unit_name for unit_id, unit_name in rows}
