from sqlalchemy.orm import Session

from app.models.supply_request import NomenclatureUserSimilar


class NomenclatureUserSimilarRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, payload: dict) -> NomenclatureUserSimilar:
        row = NomenclatureUserSimilar(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_by_id(self, similar_id: int) -> NomenclatureUserSimilar | None:
        return self.db.query(NomenclatureUserSimilar).filter(NomenclatureUserSimilar.id == similar_id).first()

    def get_by_user(self, user_id: str) -> list[NomenclatureUserSimilar]:
        return (
            self.db.query(NomenclatureUserSimilar)
            .filter(NomenclatureUserSimilar.user_id == user_id)
            .order_by(NomenclatureUserSimilar.created_at.desc())
            .all()
        )

    def update(self, similar_id: int, payload: dict) -> NomenclatureUserSimilar | None:
        row = self.get_by_id(similar_id)
        if row:
            for key, value in payload.items():
                setattr(row, key, value)
            self.db.commit()
            self.db.refresh(row)
        return row

    def delete(self, similar_id: int) -> bool:
        row = self.get_by_id(similar_id)
        if row:
            self.db.delete(row)
            self.db.commit()
            return True
        return False
