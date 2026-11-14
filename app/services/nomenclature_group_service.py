from app.models.supply_request import NomenclatureGroupCreate, NomenclatureGroupUpdate, NomenclatureRef
from app.models.warehouse import WarehouseList
from app.repositories.catalog_repository import CatalogRepository
from app.repositories.nomenclature_group_repository import NomenclatureGroupRepository
from app.repositories.request_repository import RequestRepository
from app.services.catalog_service import CatalogService


class NomenclatureGroupService:
    def __init__(self, repo: NomenclatureGroupRepository, supply_db=None) -> None:
        self.repo = repo
        self._supply_db = supply_db

    def create(self, payload: NomenclatureGroupCreate, created_by: str) -> dict:
        data = payload.model_dump()
        data["created_by"] = created_by
        row = self.repo.create(data)
        return self._serialize(row)

    def get_all(self) -> list[dict]:
        return [self._serialize(r) for r in self.repo.get_all()]

    def get_by_id(self, group_id: int) -> dict | None:
        row = self.repo.get_by_id(group_id)
        return self._serialize(row) if row else None

    def update(self, group_id: int, payload: NomenclatureGroupUpdate, user_id: str) -> dict | None:
        data = payload.model_dump(exclude_unset=True)
        row = self.repo.update(group_id, data)
        return self._serialize(row) if row else None

    def delete(self, group_id: int) -> bool:
        return self.repo.delete(group_id)

    def create_item(self, nomenclature_group_id: int, nomenclature_id: str, created_by: str) -> dict:
        data = {
            "nomenclature_group_id": nomenclature_group_id,
            "nomenclature_id": nomenclature_id,
            "created_by": created_by,
        }
        row = self.repo.create_item(data)
        return self._serialize_item(row)

    def get_item(self, item_id: str) -> dict | None:
        row = self.repo.get_item_by_id(item_id)
        return self._serialize_item(row) if row else None

    def get_items_by_group(self, group_id: int) -> list[dict]:
        rows = self.repo.get_items_by_group(group_id)
        return [self._serialize_item(r) for r in rows]

    def delete_item(self, item_id: str) -> bool:
        return self.repo.delete_item(item_id)

    def get_group_nomenclature(self, group_id: int, user_id: str | None = None) -> list[dict] | None:
        group = self.repo.get_by_id(group_id)
        if not group:
            return None
        nomenclature_ids = self.repo.get_nomenclature_ids_by_group(group_id)
        if not nomenclature_ids:
            return []
        nomenclature_rows = self._supply_db.query(NomenclatureRef).filter(NomenclatureRef.id.in_(nomenclature_ids)).all()
        catalog_service = CatalogService(CatalogRepository(self._supply_db), RequestRepository(self._supply_db))
        return catalog_service._serialize_nomenclature_rows(nomenclature_rows, user_id=user_id)

    def get_group_warehouse_list(self, group_id: int) -> dict | None:
        group = self.repo.get_by_id(group_id)
        if not group:
            return None
        nomenclature_ids = self.repo.get_nomenclature_ids_by_group(group_id)
        if not nomenclature_ids:
            return {"group": {"id": group.id, "name": group.name}, "items": []}

        from app.repositories.warehouse_repository import WarehouseRepository
        from app.services.warehouse_service import WarehouseService

        warehouse_service = WarehouseService(WarehouseRepository(self._supply_db))
        rows = warehouse_service.repo.get_list_by_nomenclature_ids(nomenclature_ids)
        items = warehouse_service._serialize_multi_warehouse_list_rows(rows)
        return {"group": {"id": group.id, "name": group.name}, "items": items}

    def _serialize(self, row) -> dict:
        return {
            "id": row.id,
            "name": row.name,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "created_by": row.created_by,
        }

    def _serialize_item(self, row) -> dict:
        return {
            "id": row.id,
            "nomenclature_group_id": row.nomenclature_group_id,
            "nomenclature_id": row.nomenclature_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "created_by": row.created_by,
        }
