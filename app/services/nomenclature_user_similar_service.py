from collections.abc import Callable

from app.repositories.nomenclature_user_similar_repository import NomenclatureUserSimilarRepository
from app.models.supply_request import NomenclatureUserSimilarCreate, NomenclatureUserSimilarUpdate


class NomenclatureUserSimilarService:
    def __init__(self, repo: NomenclatureUserSimilarRepository, nomenclature_fetcher: Callable | None = None) -> None:
        self.repo = repo
        self.nomenclature_fetcher = nomenclature_fetcher

    def create(self, payload: NomenclatureUserSimilarCreate, user_id: str) -> dict:
        data = payload.model_dump()
        data["user_id"] = user_id
        row = self.repo.create(data)
        return self._serialize(row)

    def get_by_id(self, similar_id: int) -> dict | None:
        row = self.repo.get_by_id(similar_id)
        return self._serialize(row) if row else None

    def get_by_user(self, user_id: str) -> list[dict]:
        rows = self.repo.get_by_user(user_id)
        result = [self._serialize(r) for r in rows]
        if self.nomenclature_fetcher:
            nids = set()
            for r in result:
                if r["nomenclature_id"]:
                    nids.add(r["nomenclature_id"])
            nomenclatures = {}
            for nid in nids:
                try:
                    nomenclatures[nid] = self.nomenclature_fetcher(nid)
                except Exception:
                    nomenclatures[nid] = None
            for r in result:
                r["nomenclature"] = nomenclatures.get(r["nomenclature_id"])
        return result

    def update(self, similar_id: int, payload: NomenclatureUserSimilarUpdate) -> dict | None:
        data = payload.model_dump(exclude_unset=True)
        row = self.repo.update(similar_id, data)
        return self._serialize(row) if row else None

    def delete(self, similar_id: int) -> bool:
        return self.repo.delete(similar_id)

    def _serialize(self, row) -> dict:
        return {
            "id": row.id,
            "nomenclature_id": row.nomenclature_id,
            "user_id": row.user_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
