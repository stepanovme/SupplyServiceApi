from collections.abc import Callable

from app.repositories.nomenclature_similar_repository import NomenclatureSimilarRepository
from app.models.supply_request import NomenclatureSimilarCreate, NomenclatureSimilarUpdate


class NomenclatureSimilarService:
    def __init__(self, repo: NomenclatureSimilarRepository, nomenclature_fetcher: Callable | None = None) -> None:
        self.repo = repo
        self.nomenclature_fetcher = nomenclature_fetcher

    def create(self, payload: NomenclatureSimilarCreate, created_by: str) -> dict:
        data = payload.model_dump()
        data["created_by"] = created_by
        row = self.repo.create(data)
        return self._serialize(row)

    def get_by_id(self, similar_id: int) -> dict | None:
        row = self.repo.get_by_id(similar_id)
        return self._serialize(row) if row else None

    def get_by_nomenclature(self, nomenclature_id: str) -> list[dict]:
        rows = self.repo.get_by_nomenclature(nomenclature_id)
        result = [self._serialize(r) for r in rows]
        seen: set[frozenset[str]] = set()
        unique = []
        for r in result:
            pair = frozenset([r["nomenclature_id"], r["nomenclature_simmilar_id"]])
            if pair in seen:
                continue
            seen.add(pair)
            unique.append(r)
        result = unique
        if self.nomenclature_fetcher:
            ids = set()
            for r in result:
                ids.add(r["nomenclature_id"])
                ids.add(r["nomenclature_simmilar_id"])
            nomenclatures = {}
            for nid in ids:
                try:
                    nomenclatures[nid] = self.nomenclature_fetcher(nid)
                except Exception:
                    nomenclatures[nid] = None
            for r in result:
                r["nomenclature"] = nomenclatures.get(r["nomenclature_id"])
                r["nomenclature_simmilar"] = nomenclatures.get(r["nomenclature_simmilar_id"])
        return result

    def update(self, similar_id: int, payload: NomenclatureSimilarUpdate) -> dict | None:
        data = payload.model_dump(exclude_unset=True)
        row = self.repo.update(similar_id, data)
        return self._serialize(row) if row else None

    def delete(self, similar_id: int) -> int:
        return self.repo.delete(similar_id)

    def _serialize(self, row) -> dict:
        return {
            "id": row.id,
            "nomenclature_id": row.nomenclature_id,
            "nomenclature_simmilar_id": row.nomenclature_simmilar_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "created_by": row.created_by,
        }
