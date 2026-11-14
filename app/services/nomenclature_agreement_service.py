from app.repositories.nomenclature_agreement_repository import NomenclatureAgreementRepository
from app.models.supply_request import NomenclatureAgreementCreate, NomenclatureAgreementUpdate


class NomenclatureAgreementService:
    def __init__(self, repo: NomenclatureAgreementRepository) -> None:
        self.repo = repo

    def create(self, payload: NomenclatureAgreementCreate, created_by: str) -> dict:
        data = payload.model_dump()
        data["created_by"] = created_by
        row = self.repo.create(data)
        return self._serialize(row)

    def get_by_id(self, agreement_id: str) -> dict | None:
        row = self.repo.get_by_id(agreement_id)
        return self._serialize(row) if row else None

    def get_by_nomenclature(self, nomenclature_id: str) -> list[dict]:
        rows = self.repo.get_by_nomenclature(nomenclature_id)
        return [self._serialize(r) for r in rows]

    def update(self, agreement_id: str, payload: NomenclatureAgreementUpdate) -> dict | None:
        data = payload.model_dump(exclude_unset=True)
        row = self.repo.update(agreement_id, data)
        return self._serialize(row) if row else None

    def delete(self, agreement_id: str) -> bool:
        return self.repo.delete(agreement_id)

    def _serialize(self, row) -> dict:
        return {
            "id": row.id,
            "nomenclature_id": row.nomenclature_id,
            "agreement": row.agreement,
            "type": row.type,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "created_by": row.created_by,
        }
