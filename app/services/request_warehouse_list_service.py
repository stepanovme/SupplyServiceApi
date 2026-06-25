from __future__ import annotations

from fastapi import HTTPException, status

from app.models.request_warehouse_list import RequestWarehouseListCreate, RequestWarehouseListUpdate
from app.repositories.request_warehouse_list_repository import RequestWarehouseListRepository


class RequestWarehouseListService:
    def __init__(self, repo: RequestWarehouseListRepository) -> None:
        self.repo = repo

    def get_all(self):
        return [self._serialize(row) for row in self.repo.get_all()]

    def get_by_id(self, row_id: str):
        row = self.repo.get_by_id(row_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request warehouse list row not found")
        return self._serialize(row)

    def get_by_request_id(self, request_id: int):
        return [self._serialize(row) for row in self.repo.get_by_request_id(request_id)]

    def create(self, payload: RequestWarehouseListCreate, user_id: str):
        data = self._normalize(payload.model_dump(exclude_unset=True))
        data["created_by"] = user_id
        row = self.repo.create(data)
        return self._serialize(row)

    def update(self, row_id: str, payload: RequestWarehouseListUpdate):
        row = self.repo.get_by_id(row_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request warehouse list row not found")
        data = self._normalize(payload.model_dump(exclude_unset=True))
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save(row)
        return self._serialize(updated)

    def delete(self, row_id: str):
        row = self.repo.get_by_id(row_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request warehouse list row not found")
        self.repo.delete(row)
        return None

    @staticmethod
    def _serialize(row) -> dict:
        return {
            "request_warehouse_list_id": row.request_warehouse_list_id,
            "request_id": row.request_id,
            "request_item_id": row.request_item_id,
            "warehouse_id": row.warehouse_id,
            "warehouse_list_id": row.warehouse_list_id,
            "request_qantity": row.request_qantity,
            "warehouse_quantity": row.warehouse_quantity,
            "created_at": row.created_at,
            "created_by": row.created_by,
        }

    @staticmethod
    def _normalize(data: dict) -> dict:
        normalized = dict(data)
        for field_name in ("request_item_id", "warehouse_id", "warehouse_list_id"):
            if normalized.get(field_name) == "":
                normalized[field_name] = None
        return normalized
