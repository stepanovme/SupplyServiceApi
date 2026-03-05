from fastapi import HTTPException, status

from app.models.supply_request import (
    NomenclatureCreate,
    NomenclatureUpdate,
    WarehouseCategoryCreate,
    WarehouseCategoryUpdate,
)
from app.repositories.catalog_repository import CatalogRepository
from app.repositories.request_repository import RequestRepository


class CatalogService:
    def __init__(self, repo: CatalogRepository, request_repo: RequestRepository) -> None:
        self.repo = repo
        self.request_repo = request_repo

    def get_units(self):
        return [{"id": item.id, "name": item.name} for item in self.repo.get_units()]

    def get_warehouse_categories(self):
        return [
            {
                "id": item.id,
                "name": item.name,
                "parent_id": item.parent_id,
            }
            for item in self.repo.get_warehouse_categories()
        ]

    def create_warehouse_category(self, payload: WarehouseCategoryCreate):
        data = payload.model_dump(exclude_unset=True)
        item = self.repo.create_warehouse_category(data)
        return {
            "id": item.id,
            "name": item.name,
            "parent_id": item.parent_id,
        }

    def update_warehouse_category(self, category_id: str, payload: WarehouseCategoryUpdate):
        item = self.repo.get_warehouse_category_by_id(category_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Warehouse category not found",
            )

        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(item, key, value)

        updated = self.repo.save_warehouse_category(item)
        return {
            "id": updated.id,
            "name": updated.name,
            "parent_id": updated.parent_id,
        }

    def get_nomenclature(self, search: str | None = None):
        rows = self.repo.get_nomenclature(search)
        return self._serialize_nomenclature_rows(rows)

    def get_nomenclature_by_id(self, nomenclature_id: str):
        row = self.repo.get_nomenclature_by_id(nomenclature_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nomenclature not found")
        rows = self._serialize_nomenclature_rows([row])
        return rows[0]

    def create_nomenclature(self, payload: NomenclatureCreate, user_id: str):
        data = payload.model_dump(exclude_unset=True)
        data["created_by"] = user_id
        row = self.repo.create_nomenclature(data)
        rows = self._serialize_nomenclature_rows([row])
        return rows[0]

    def update_nomenclature(self, nomenclature_id: str, payload: NomenclatureUpdate):
        row = self.repo.get_nomenclature_by_id(nomenclature_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nomenclature not found")

        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)

        updated = self.repo.save_nomenclature(row)
        rows = self._serialize_nomenclature_rows([updated])
        return rows[0]

    def delete_nomenclature(self, nomenclature_id: str):
        row = self.repo.get_nomenclature_by_id(nomenclature_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nomenclature not found")
        self.repo.delete_nomenclature(row)
        return None

    def _serialize_nomenclature_rows(self, rows):
        unit_ids = [item.unit_id for item in rows if item.unit_id]
        category_ids = [item.warehouse_category_id for item in rows if item.warehouse_category_id]
        units = self.request_repo.get_units_by_ids(unit_ids)
        categories = self.request_repo.get_warehouse_categories_by_ids(category_ids)
        units_by_id = {item.id: item for item in units}
        categories_by_id = {item.id: item for item in categories}

        result = []
        for item in rows:
            unit = units_by_id.get(item.unit_id)
            category = categories_by_id.get(item.warehouse_category_id)
            result.append(
                {
                    "id": item.id,
                    "name": item.name,
                    "description": item.description,
                    "article": item.article,
                    "unit_id": item.unit_id,
                    "warehouse_category_id": item.warehouse_category_id,
                    "unit": None if not unit else {"id": unit.id, "name": unit.name},
                    "warehouse_category": None
                    if not category
                    else {
                        "id": category.id,
                        "name": category.name,
                        "parent_id": category.parent_id,
                    },
                    "length": item.length,
                    "width": item.width,
                    "height": item.height,
                    "weight": item.weight,
                    "created_at": item.created_at,
                    "created_by": item.created_by,
                }
            )

        return result
