from sqlalchemy.orm import Session

from app.models.supply_request import NomenclatureAgreement


class NomenclatureAgreementRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, payload: dict) -> NomenclatureAgreement:
        row = NomenclatureAgreement(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_by_id(self, agreement_id: str) -> NomenclatureAgreement | None:
        return self.db.query(NomenclatureAgreement).filter(NomenclatureAgreement.id == agreement_id).first()

    def get_by_nomenclature(self, nomenclature_id: str) -> list[NomenclatureAgreement]:
        return (
            self.db.query(NomenclatureAgreement)
            .filter(NomenclatureAgreement.nomenclature_id == nomenclature_id)
            .order_by(NomenclatureAgreement.created_at.desc())
            .all()
        )

    def update(self, agreement_id: str, payload: dict) -> NomenclatureAgreement | None:
        row = self.get_by_id(agreement_id)
        if row:
            for key, value in payload.items():
                setattr(row, key, value)
            self.db.commit()
            self.db.refresh(row)
        return row

    def delete(self, agreement_id: str) -> bool:
        row = self.get_by_id(agreement_id)
        if not row:
            return False
        self.db.delete(row)
        self.db.commit()
        return True
