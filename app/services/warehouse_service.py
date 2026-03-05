from fastapi import HTTPException, status

from app.models.warehouse import WarehouseCreate, WarehouseUpdate
from app.repositories.warehouse_repository import WarehouseRepository

TYPE_NAMES = {
    "warehouse": "объектный",
    "on-site warehouse": "приобъектный",
}


class WarehouseService:
    def __init__(self, repo: WarehouseRepository) -> None:
        self.repo = repo

    def get_all(self):
        rows = self.repo.get_all()
        return [self._to_response(row) for row in rows]

    def create(self, payload: WarehouseCreate):
        data = payload.model_dump(exclude_unset=True)
        created = self.repo.create(data)
        return self._to_response(created)

    def update(self, warehouse_id: str, payload: WarehouseUpdate):
        row = self.repo.get_by_id(warehouse_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse not found")

        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)

        updated = self.repo.save(row)
        return self._to_response(updated)

    def delete(self, warehouse_id: str):
        row = self.repo.get_by_id(warehouse_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse not found")
        self.repo.delete(row)
        return None

    @staticmethod
    def _to_response(row):
        return {
            "id": row.id,
            "name": row.name,
            "type": row.type,
            "type_name": TYPE_NAMES.get(row.type),
            "object_levels_id": row.object_levels_id,
        }
