import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceItem, InvoiceLog, InvoicePayment
from app.models.supply_request import StatusRef, SupplyRequest, UnitRef


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

    def get_invoices(self) -> list[Invoice]:
        return self.db.query(Invoice).order_by(Invoice.id.desc()).all()

    def get_invoices_by_ids(self, invoice_ids: list[int]) -> list[Invoice]:
        if not invoice_ids:
            return []
        return self.db.query(Invoice).filter(Invoice.id.in_(invoice_ids)).order_by(Invoice.id.desc()).all()

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

    def get_request_names_by_ids(self, request_ids: list[int]) -> dict[int, str | None]:
        if not request_ids:
            return {}
        rows = (
            self.db.query(SupplyRequest.id, SupplyRequest.name)
            .filter(SupplyRequest.id.in_(list({rid for rid in request_ids if rid is not None})))
            .all()
        )
        return {row_id: row_name for row_id, row_name in rows}

    def get_requests_meta_by_ids(self, request_ids: list[int]) -> dict[int, dict]:
        unique_ids = list({rid for rid in request_ids if rid is not None})
        if not unique_ids:
            return {}
        rows = (
            self.db.query(SupplyRequest.id, SupplyRequest.name, SupplyRequest.object_levels_id)
            .filter(SupplyRequest.id.in_(unique_ids))
            .all()
        )
        return {
            row_id: {"name": row_name, "object_levels_id": object_levels_id}
            for row_id, row_name, object_levels_id in rows
        }

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

    def delete_invoice_items_by_invoice_id(self, invoice_id: int) -> None:
        (
            self.db.query(InvoiceItem)
            .filter(InvoiceItem.invoice_id == invoice_id)
            .delete(synchronize_session=False)
        )
        self.db.commit()

    def get_invoice_logs(self, invoice_id: int) -> list[InvoiceLog]:
        return (
            self.db.query(InvoiceLog)
            .filter(InvoiceLog.invoice_id == invoice_id)
            .order_by(InvoiceLog.id.asc())
            .all()
        )

    def create_invoice_log(self, invoice_id: int, payload: dict) -> InvoiceLog:
        row = InvoiceLog(id=str(uuid.uuid4()), invoice_id=invoice_id, **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_invoice_log_by_id(self, invoice_id: int, log_id: str) -> InvoiceLog | None:
        return (
            self.db.query(InvoiceLog)
            .filter(
                InvoiceLog.invoice_id == invoice_id,
                InvoiceLog.id == log_id,
            )
            .first()
        )

    def save_invoice_log(self, row: InvoiceLog) -> InvoiceLog:
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_invoice_logs_by_user(self, user_id: str) -> list[InvoiceLog]:
        return (
            self.db.query(InvoiceLog)
            .filter(InvoiceLog.user_id == user_id)
            .order_by(InvoiceLog.id.desc())
            .all()
        )

    def get_invoice_logs_by_invoice_ids(self, invoice_ids: list[int]) -> list[InvoiceLog]:
        if not invoice_ids:
            return []
        return (
            self.db.query(InvoiceLog)
            .filter(InvoiceLog.invoice_id.in_(invoice_ids))
            .order_by(InvoiceLog.id.asc())
            .all()
        )

    def get_invoice_payments(self, invoice_id: int) -> list[InvoicePayment]:
        return (
            self.db.query(InvoicePayment)
            .filter(InvoicePayment.invoice_id == invoice_id)
            .order_by(InvoicePayment.created_at.asc(), InvoicePayment.id.asc())
            .all()
        )

    def create_invoice_payment(self, invoice_id: int, payload: dict) -> InvoicePayment:
        row = InvoicePayment(id=str(uuid.uuid4()), invoice_id=invoice_id, **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_invoice_payment_by_id(self, invoice_id: int, payment_id: str) -> InvoicePayment | None:
        return (
            self.db.query(InvoicePayment)
            .filter(
                InvoicePayment.invoice_id == invoice_id,
                InvoicePayment.id == payment_id,
            )
            .first()
        )

    def save_invoice_payment(self, row: InvoicePayment) -> InvoicePayment:
        row.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_invoice_payments_by_invoice_ids(self, invoice_ids: list[int]) -> list[InvoicePayment]:
        if not invoice_ids:
            return []
        return (
            self.db.query(InvoicePayment)
            .filter(InvoicePayment.invoice_id.in_(invoice_ids))
            .order_by(InvoicePayment.created_at.asc(), InvoicePayment.id.asc())
            .all()
        )

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
