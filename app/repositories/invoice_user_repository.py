from sqlalchemy.orm import Session

from app.models.invoice_user import InvoiceUser


class InvoiceUserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(self) -> list[InvoiceUser]:
        return self.db.query(InvoiceUser).all()

    def get_by_id(self, item_id: int) -> InvoiceUser | None:
        return self.db.query(InvoiceUser).filter(InvoiceUser.id == item_id).first()

    def get_by_invoice_id(self, invoice_id: int) -> list[InvoiceUser]:
        return self.db.query(InvoiceUser).filter(InvoiceUser.invoice_id == invoice_id).all()

    def get_by_invoice_ids(self, invoice_ids: list[int]) -> list[InvoiceUser]:
        if not invoice_ids:
            return []
        return self.db.query(InvoiceUser).filter(InvoiceUser.invoice_id.in_(invoice_ids)).all()

    def get_invoice_ids_by_user_id_and_role(self, user_id: str, role: str) -> list[int]:
        rows = (
            self.db.query(InvoiceUser.invoice_id)
            .filter(
                InvoiceUser.user_id == user_id,
                InvoiceUser.role == role,
            )
            .all()
        )
        return [row[0] for row in rows]

    def create(self, item: InvoiceUser) -> InvoiceUser:
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def save(self, item: InvoiceUser) -> InvoiceUser:
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete(self, item: InvoiceUser) -> None:
        self.db.delete(item)
        self.db.commit()
