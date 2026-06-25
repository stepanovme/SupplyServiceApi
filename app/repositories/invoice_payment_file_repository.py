from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.invoice_payment_file import InvoicePaymentFile


class InvoicePaymentFileRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_payment_id(self, payment_id: str) -> list[InvoicePaymentFile]:
        return (
            self.db.query(InvoicePaymentFile)
            .filter(InvoicePaymentFile.invoice_payment_id == payment_id)
            .order_by(InvoicePaymentFile.uploaded_at.desc(), InvoicePaymentFile.id.desc())
            .all()
        )

    def get_by_id(self, row_id: str) -> InvoicePaymentFile | None:
        return self.db.query(InvoicePaymentFile).filter(InvoicePaymentFile.id == row_id).first()

    def create(self, payment_id: str, payload: dict) -> InvoicePaymentFile:
        row = InvoicePaymentFile(id=str(uuid.uuid4()), invoice_payment_id=payment_id, **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: InvoicePaymentFile) -> InvoicePaymentFile:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, row: InvoicePaymentFile) -> None:
        self.db.delete(row)
        self.db.commit()
