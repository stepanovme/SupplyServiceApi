from __future__ import annotations

from fastapi import HTTPException, status

from app.models.request_specification import RequestSpecificationCreate, RequestSpecificationUpdate
from app.repositories.request_specification_repository import RequestSpecificationRepository


class RequestSpecificationService:
    def __init__(self, repo: RequestSpecificationRepository) -> None:
        self.repo = repo

    def get_all(self):
        return self._serialize_many(self.repo.get_all())

    def get_by_id(self, row_id: str):
        row = self.repo.get_by_id(row_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request specification not found")
        return self._serialize(row)

    def get_by_request_id(self, request_id: int):
        return self._serialize_many(self.repo.get_by_request_id(request_id))

    def get_by_specification_id(self, specification_id: str):
        return self._serialize_many(self.repo.get_by_specification_id(specification_id))

    def create(self, payload: RequestSpecificationCreate, user_id: str):
        data = self._normalize(payload.model_dump(exclude_unset=True))
        data["created_by"] = user_id
        row = self.repo.create(data)
        return self._serialize(row)

    def update(self, row_id: str, payload: RequestSpecificationUpdate):
        row = self.repo.get_by_id(row_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request specification not found")
        data = self._normalize(payload.model_dump(exclude_unset=True))
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save(row)
        return self._serialize(updated)

    def delete(self, row_id: str):
        row = self.repo.get_by_id(row_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request specification not found")
        self.repo.delete(row)
        return None

    def _serialize_many(self, rows) -> list[dict]:
        spec_item_ids = [row.specification_item_id for row in rows]
        names = self.repo.get_specification_item_names(spec_item_ids) if spec_item_ids else {}
        return [self._serialize(row, names) for row in rows]

    @staticmethod
    def _serialize(row, names: dict | None = None) -> dict:
        return {
            "request_specification_id": row.request_specification_id,
            "request_id": row.request_id,
            "request_item_id": row.request_item_id,
            "specification_id": row.specification_id,
            "specification_item_id": row.specification_item_id,
            "specification_item_name": (names or {}).get(row.specification_item_id),
            "created_at": row.created_at,
            "created_by": row.created_by,
        }

    @staticmethod
    def _normalize(data: dict) -> dict:
        normalized = dict(data)
        for field_name in ("request_item_id", "specification_id", "specification_item_id"):
            if normalized.get(field_name) == "":
                normalized[field_name] = None
        return normalized
