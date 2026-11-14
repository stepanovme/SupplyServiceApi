from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.purchase_receipt import PurchaseReceiptCategory
from app.models.receipt_category import ReceiptCategory


class ReceiptCategoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, category_id: str) -> ReceiptCategory | None:
        return self.db.query(ReceiptCategory).filter(ReceiptCategory.id == category_id).first()

    def get_available(self, user_id: str, scope: str = "all") -> list[ReceiptCategory]:
        """Standard categories (owner NULL) and/or the user's own."""
        q = self.db.query(ReceiptCategory)
        if scope == "system":
            q = q.filter(ReceiptCategory.owner_user_id.is_(None))
        elif scope == "mine":
            q = q.filter(ReceiptCategory.owner_user_id == user_id)
        else:
            q = q.filter(or_(ReceiptCategory.owner_user_id.is_(None), ReceiptCategory.owner_user_id == user_id))
        # standard first, then personal, each alphabetically
        return q.order_by(ReceiptCategory.owner_user_id.is_not(None), ReceiptCategory.name).all()

    def find_by_name(self, name: str, owner_user_id: str | None) -> ReceiptCategory | None:
        """Name lookup inside one scope; the column collation is case-insensitive."""
        q = self.db.query(ReceiptCategory).filter(ReceiptCategory.name == name)
        q = q.filter(ReceiptCategory.owner_user_id.is_(None) if owner_user_id is None else ReceiptCategory.owner_user_id == owner_user_id)
        return q.first()

    def count_receipts(self, category_id: str) -> int:
        return (
            self.db.query(func.count(PurchaseReceiptCategory.receipt_id))
            .filter(PurchaseReceiptCategory.category_id == category_id)
            .scalar()
            or 0
        )

    def add(self, row) -> None:
        self.db.add(row)

    def delete(self, row) -> None:
        self.db.delete(row)

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def refresh(self, row) -> None:
        self.db.refresh(row)
