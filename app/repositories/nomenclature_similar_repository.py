from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.supply_request import NomenclatureSimilar


class NomenclatureSimilarRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, payload: dict) -> NomenclatureSimilar:
        row = NomenclatureSimilar(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_by_id(self, similar_id: int) -> NomenclatureSimilar | None:
        return self.db.query(NomenclatureSimilar).filter(NomenclatureSimilar.id == similar_id).first()

    def get_by_nomenclature(self, nomenclature_id: str) -> list[NomenclatureSimilar]:
        return (
            self.db.query(NomenclatureSimilar)
            .filter(
                or_(
                    NomenclatureSimilar.nomenclature_id == nomenclature_id,
                    NomenclatureSimilar.nomenclature_simmilar_id == nomenclature_id,
                )
            )
            .order_by(NomenclatureSimilar.created_at.desc())
            .all()
        )

    def update(self, similar_id: int, payload: dict) -> NomenclatureSimilar | None:
        row = self.get_by_id(similar_id)
        if row:
            for key, value in payload.items():
                setattr(row, key, value)
            self.db.commit()
            self.db.refresh(row)
        return row

    def delete(self, similar_id: int) -> int:
        row = self.get_by_id(similar_id)
        if not row:
            return 0
        nid1 = row.nomenclature_id
        nid2 = row.nomenclature_simmilar_id
        if nid1 == nid2:
            self.db.delete(row)
            self.db.commit()
            return 1
        deleted = (
            self.db.query(NomenclatureSimilar)
            .filter(
                or_(
                    NomenclatureSimilar.nomenclature_id == nid1,
                    NomenclatureSimilar.nomenclature_simmilar_id == nid1,
                ),
                or_(
                    NomenclatureSimilar.nomenclature_id == nid2,
                    NomenclatureSimilar.nomenclature_simmilar_id == nid2,
                ),
            )
            .delete(synchronize_session=False)
        )
        self.db.commit()
        return deleted
