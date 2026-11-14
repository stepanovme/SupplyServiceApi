from sqlalchemy.orm import Session

from app.models.business_card import BusinessCard


class BusinessCardRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, card_id: str) -> BusinessCard | None:
        return self.db.query(BusinessCard).filter(BusinessCard.id == card_id).first()

    def get_by_ids(self, card_ids: list[str]) -> list[BusinessCard]:
        if not card_ids:
            return []
        return self.db.query(BusinessCard).filter(BusinessCard.id.in_(card_ids)).all()

    def get_by_bank_business_card_id(self, settings_api_bank_id: str, bank_business_card_id: str) -> BusinessCard | None:
        return (
            self.db.query(BusinessCard)
            .filter(
                BusinessCard.settings_api_bank_id == settings_api_bank_id,
                BusinessCard.bank_business_card_id == bank_business_card_id,
            )
            .first()
        )

    def get_active_by_last4(self, card_last4: str) -> list[BusinessCard]:
        return (
            self.db.query(BusinessCard)
            .filter(BusinessCard.card_last4 == card_last4, BusinessCard.is_active.is_(True))
            .all()
        )

    def get_list(
        self,
        holder_user_id: str | None = None,
        settings_api_bank_id: str | None = None,
        is_active: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[BusinessCard]:
        q = self.db.query(BusinessCard)
        if holder_user_id is not None:
            q = q.filter(BusinessCard.holder_user_id == holder_user_id)
        if settings_api_bank_id is not None:
            q = q.filter(BusinessCard.settings_api_bank_id == settings_api_bank_id)
        if is_active is not None:
            q = q.filter(BusinessCard.is_active == is_active)
        return q.order_by(BusinessCard.created_at.desc()).offset(offset).limit(limit).all()

    def create(self, row: BusinessCard) -> BusinessCard:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: BusinessCard) -> BusinessCard:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, row: BusinessCard) -> None:
        self.db.delete(row)
        self.db.commit()
