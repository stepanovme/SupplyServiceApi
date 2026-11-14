from datetime import datetime

from sqlalchemy.orm import Session

from app.models.business_card import ExtractBusinessCard
from app.models.extract_item import ExtractItem


class ExtractBusinessCardRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, item_id: str) -> ExtractBusinessCard | None:
        return self.db.query(ExtractBusinessCard).filter(ExtractBusinessCard.id == item_id).first()

    def get_by_extract_id(self, extract_id: str) -> ExtractBusinessCard | None:
        return self.db.query(ExtractBusinessCard).filter(ExtractBusinessCard.extract_id == extract_id).first()

    def get_by_extract_ids(self, extract_ids: list[str]) -> list[ExtractBusinessCard]:
        if not extract_ids:
            return []
        return self.db.query(ExtractBusinessCard).filter(ExtractBusinessCard.extract_id.in_(extract_ids)).all()

    def get_by_card_ids(self, card_ids: list[str]) -> list[ExtractBusinessCard]:
        if not card_ids:
            return []
        return self.db.query(ExtractBusinessCard).filter(ExtractBusinessCard.business_card_id.in_(card_ids)).all()

    def get_list(
        self,
        business_card_id: str | None = None,
        extract_id: str | None = None,
        object_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ExtractBusinessCard]:
        q = self.db.query(ExtractBusinessCard)
        if business_card_id is not None:
            q = q.filter(ExtractBusinessCard.business_card_id == business_card_id)
        if extract_id is not None:
            q = q.filter(ExtractBusinessCard.extract_id == extract_id)
        if object_id is not None:
            q = q.filter(ExtractBusinessCard.object_id == object_id)
        return q.offset(offset).limit(limit).all()

    def create(self, row: ExtractBusinessCard) -> ExtractBusinessCard:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: ExtractBusinessCard) -> ExtractBusinessCard:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, row: ExtractBusinessCard) -> None:
        self.db.delete(row)
        self.db.commit()

    def get_spending_rows(
        self,
        card_ids: list[str],
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[tuple[ExtractBusinessCard, ExtractItem]]:
        if not card_ids:
            return []
        q = (
            self.db.query(ExtractBusinessCard, ExtractItem)
            .join(ExtractItem, ExtractItem.id == ExtractBusinessCard.extract_id)
            .filter(ExtractBusinessCard.business_card_id.in_(card_ids))
        )
        if date_from is not None:
            q = q.filter(ExtractItem.operationDate >= date_from)
        if date_to is not None:
            q = q.filter(ExtractItem.operationDate <= date_to)
        return q.all()

    def get_rows_by_object_id(
        self,
        object_id: str,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[tuple[ExtractBusinessCard, ExtractItem]]:
        q = (
            self.db.query(ExtractBusinessCard, ExtractItem)
            .join(ExtractItem, ExtractItem.id == ExtractBusinessCard.extract_id)
            .filter(ExtractBusinessCard.object_id == object_id)
        )
        if date_from is not None:
            q = q.filter(ExtractItem.operationDate >= date_from)
        if date_to is not None:
            q = q.filter(ExtractItem.operationDate <= date_to)
        return q.order_by(ExtractItem.operationDate.desc()).all()

    def get_unmatched_extract_items(
        self,
        limit: int = 50,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[ExtractItem]:
        linked_ids = self.db.query(ExtractBusinessCard.extract_id).subquery()
        q = (
            self.db.query(ExtractItem)
            .filter(ExtractItem.id.notin_(self.db.query(linked_ids.c.extract_id)))
            .filter(ExtractItem.paymentPurpose.is_not(None))
        )
        if date_from is not None:
            q = q.filter(ExtractItem.operationDate >= date_from)
        if date_to is not None:
            q = q.filter(ExtractItem.operationDate <= date_to)
        return q.order_by(ExtractItem.operationDate.desc()).limit(limit).all()
