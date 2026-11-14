from datetime import datetime

from sqlalchemy.orm import Session

from app.models.extract_item import ExtractItem
from app.models.invoice import Invoice, InvoicePayment
from app.models.invoice_payment_extract import InvoicePaymentExtract


class InvoicePaymentExtractRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, item_id: str) -> InvoicePaymentExtract | None:
        return self.db.query(InvoicePaymentExtract).filter(InvoicePaymentExtract.id == item_id).first()

    def get_by_extract_id(self, extract_id: str) -> InvoicePaymentExtract | None:
        """Any one link of the row (first by creation) - enough to tell "is it linked at all"."""
        return (
            self.db.query(InvoicePaymentExtract)
            .filter(InvoicePaymentExtract.extract_id == extract_id)
            .order_by(InvoicePaymentExtract.created_at, InvoicePaymentExtract.id)
            .first()
        )

    def get_links_by_extract_id(self, extract_id: str) -> list[InvoicePaymentExtract]:
        return (
            self.db.query(InvoicePaymentExtract)
            .filter(InvoicePaymentExtract.extract_id == extract_id)
            .order_by(InvoicePaymentExtract.created_at, InvoicePaymentExtract.id)
            .all()
        )

    def get_pair(self, extract_id: str, payment_id: str) -> InvoicePaymentExtract | None:
        return (
            self.db.query(InvoicePaymentExtract)
            .filter(
                InvoicePaymentExtract.extract_id == extract_id,
                InvoicePaymentExtract.invoice_payment_id == payment_id,
            )
            .first()
        )

    def get_by_extract_ids(self, extract_ids: list[str]) -> list[InvoicePaymentExtract]:
        if not extract_ids:
            return []
        return (
            self.db.query(InvoicePaymentExtract)
            .filter(InvoicePaymentExtract.extract_id.in_(extract_ids))
            .order_by(InvoicePaymentExtract.created_at, InvoicePaymentExtract.id)
            .all()
        )

    def get_by_payment_ids(self, payment_ids: list[str]) -> list[InvoicePaymentExtract]:
        if not payment_ids:
            return []
        return (
            self.db.query(InvoicePaymentExtract)
            .filter(InvoicePaymentExtract.invoice_payment_id.in_(payment_ids))
            .all()
        )

    def get_list(
        self,
        extract_id: str | None = None,
        invoice_id: int | None = None,
        invoice_payment_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[InvoicePaymentExtract]:
        q = self.db.query(InvoicePaymentExtract)
        if extract_id is not None:
            q = q.filter(InvoicePaymentExtract.extract_id == extract_id)
        if invoice_payment_id is not None:
            q = q.filter(InvoicePaymentExtract.invoice_payment_id == invoice_payment_id)
        if invoice_id is not None:
            q = q.join(InvoicePayment, InvoicePayment.id == InvoicePaymentExtract.invoice_payment_id).filter(
                InvoicePayment.invoice_id == invoice_id
            )
        return q.order_by(InvoicePaymentExtract.created_at.desc()).offset(offset).limit(limit).all()

    def get_payment_by_id(self, payment_id: str) -> InvoicePayment | None:
        return self.db.query(InvoicePayment).filter(InvoicePayment.id == payment_id).first()

    def get_payments_by_ids(self, payment_ids: list[str]) -> list[InvoicePayment]:
        if not payment_ids:
            return []
        return self.db.query(InvoicePayment).filter(InvoicePayment.id.in_(payment_ids)).all()

    def get_invoices_by_ids(self, invoice_ids: list[int]) -> list[Invoice]:
        if not invoice_ids:
            return []
        return self.db.query(Invoice).filter(Invoice.id.in_(invoice_ids)).all()

    def create(self, row: InvoicePaymentExtract) -> InvoicePaymentExtract:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, row: InvoicePaymentExtract) -> None:
        self.db.delete(row)
        self.db.commit()

    def get_unmatched_debit_extract_items(
        self,
        limit: int = 50,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[ExtractItem]:
        """DEBIT rows that mention an invoice ("счет"/"счёт" - the column's *_ai_ci collation
        makes LIKE treat е/ё alike) and aren't linked to any payment yet. This is only a cheap
        pre-filter; the real parsing happens in invoice_reference_parser."""
        linked_ids = self.db.query(InvoicePaymentExtract.extract_id)
        q = (
            self.db.query(ExtractItem)
            .filter(ExtractItem.direction == "DEBIT")
            .filter(ExtractItem.paymentPurpose.like("%счет%"))
            .filter(ExtractItem.id.notin_(linked_ids))
        )
        if date_from is not None:
            q = q.filter(ExtractItem.operationDate >= date_from)
        if date_to is not None:
            q = q.filter(ExtractItem.operationDate <= date_to)
        return q.order_by(ExtractItem.operationDate.desc()).limit(limit).all()
