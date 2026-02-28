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

    def get_nomenclature(self, search: str | None = None):
        rows = self.repo.get_nomenclature(search)

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
                }
            )

        return result
