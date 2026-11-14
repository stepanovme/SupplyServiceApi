from datetime import datetime

from sqlalchemy.orm import Session

from app.models.business_card import ExtractBusinessCard
from app.models.extract_item import ExtractItem


class ExtractItemRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, item_id: str) -> ExtractItem | None:
        return self.db.query(ExtractItem).filter(ExtractItem.id == item_id).first()

    def get_by_ids(self, item_ids: list[str]) -> list[ExtractItem]:
        if not item_ids:
            return []
        return self.db.query(ExtractItem).filter(ExtractItem.id.in_(item_ids)).all()

    def find_by_external_id(self, bank_type: str, external_id: str) -> ExtractItem | None:
        return (
            self.db.query(ExtractItem)
            .filter(ExtractItem.bank_type == bank_type, ExtractItem.external_id == external_id)
            .first()
        )

    def find_legacy_duplicate(
        self,
        bank_type: str | None,
        operation_date: datetime | None,
        amount: float | None,
        direction: str | None,
        payment_purpose: str | None,
        payee_inn: str | None,
        payer_inn: str | None,
        payee_account: str | None,
    ) -> ExtractItem | None:
        """A row loaded BEFORE external_id existed (external_id IS NULL) that is the same
        operation by content. Used so re-loading an overlapping period doesn't duplicate old
        rows, and so the old row can get its external_id back-filled."""
        q = self.db.query(ExtractItem).filter(
            ExtractItem.external_id.is_(None),
            ExtractItem.operationDate == operation_date,
            ExtractItem.amount == amount,
            ExtractItem.direction == direction,
            ExtractItem.paymentPurpose == payment_purpose,
            ExtractItem.payeeInn == payee_inn,
            ExtractItem.payerInn == payer_inn,
            ExtractItem.payeeAccount == payee_account,
        )
        if bank_type:
            q = q.filter((ExtractItem.bank_type == bank_type) | (ExtractItem.bank_type.is_(None)))
        return q.first()

    def find_duplicate(
        self,
        operation_date: datetime | None,
        amount: float | None,
        direction: str | None,
        payment_purpose: str | None,
        payee_inn: str | None,
        payer_inn: str | None,
        payee_account: str | None,
        account_number: str | None = None,
    ) -> ExtractItem | None:
        """Content-based dedup fallback, for sources with no stable external_id (e.g. the
        Excel parsers). Prefer find_by_external_id whenever the source provides a native
        transaction id - content matching can't tell apart two genuinely different
        operations that happen to share the same date/amount/purpose/parties."""
        return (
            self.db.query(ExtractItem)
            .filter(
                ExtractItem.operationDate == operation_date,
                ExtractItem.amount == amount,
                ExtractItem.direction == direction,
                ExtractItem.paymentPurpose == payment_purpose,
                ExtractItem.payeeInn == payee_inn,
                ExtractItem.payerInn == payer_inn,
                ExtractItem.payeeAccount == payee_account,
                ExtractItem.account_number == account_number,
            )
            .first()
        )

    def create(self, row: ExtractItem) -> ExtractItem:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: ExtractItem) -> ExtractItem:
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_by_object_id(
        self,
        object_id: str,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        exclude_business_cards: bool = True,
    ) -> list[ExtractItem]:
        """Rows attached straight to the object (extract_items.object_id). Rows that belong to a
        business card are left out by default - the card flow has its own by-object endpoint."""
        q = self.db.query(ExtractItem).filter(ExtractItem.object_id == object_id)
        if exclude_business_cards:
            q = q.filter(ExtractItem.id.notin_(self.db.query(ExtractBusinessCard.extract_id)))
        if date_from is not None:
            q = q.filter(ExtractItem.operationDate >= date_from)
        if date_to is not None:
            q = q.filter(ExtractItem.operationDate <= date_to)
        return q.order_by(ExtractItem.operationDate.desc()).all()

    def get_list(
        self,
        payee_id_missing: bool | None = None,
        payer_id_missing: bool | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        account_number: str | None = None,
        bank_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
        object_id: str | None = None,
        object_missing: bool | None = None,
    ) -> list[ExtractItem]:
        q = self.db.query(ExtractItem)
        if payee_id_missing is True:
            q = q.filter(ExtractItem.payee_id.is_(None))
        elif payee_id_missing is False:
            q = q.filter(ExtractItem.payee_id.is_not(None))
        if payer_id_missing is True:
            q = q.filter(ExtractItem.payer_id.is_(None))
        elif payer_id_missing is False:
            q = q.filter(ExtractItem.payer_id.is_not(None))
        if date_from is not None:
            q = q.filter(ExtractItem.operationDate >= date_from)
        if date_to is not None:
            q = q.filter(ExtractItem.operationDate <= date_to)
        if account_number is not None:
            q = q.filter(ExtractItem.account_number == account_number)
        if bank_type is not None:
            q = q.filter(ExtractItem.bank_type == bank_type)
        if object_id is not None:
            q = q.filter(ExtractItem.object_id == object_id)
        if object_missing is True:
            q = q.filter(ExtractItem.object_id.is_(None))
        elif object_missing is False:
            q = q.filter(ExtractItem.object_id.is_not(None))
        return q.order_by(ExtractItem.operationDate.desc()).offset(offset).limit(limit).all()
