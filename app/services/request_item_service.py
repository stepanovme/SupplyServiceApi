from fastapi import HTTPException, status

from app.models.supply_request import RequestItemCreate, RequestItemUpdate
from app.repositories.request_repository import RequestRepository


class RequestItemService:
    def __init__(self, repo: RequestRepository) -> None:
        self.repo = repo

    def create(self, request_id: int, data: RequestItemCreate):
        if not self.repo.request_exists(request_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

        payload = data.model_dump(exclude_unset=True)
        if "num" not in payload or payload["num"] is None:
            payload["num"] = self.repo.get_next_request_item_num(request_id)

        if "quantity" not in payload or payload["quantity"] is None:
            payload["quantity"] = 1.0

        nomenclature_id = payload.get("nomenclature_id")
        if nomenclature_id:
            nomenclature = self.repo.get_nomenclature_by_id(nomenclature_id)
            if not nomenclature:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Nomenclature not found",
                )
            if not payload.get("unit_id"):
                payload["unit_id"] = nomenclature.unit_id
            if not payload.get("warehouse_category_id"):
                payload["warehouse_category_id"] = nomenclature.warehouse_category_id
            if not payload.get("name"):
                payload["name"] = nomenclature.name

        created = self.repo.create_request_item(request_id, payload)
        return self._to_response(created)

    def update(self, request_id: int, item_id: str, data: RequestItemUpdate):
        if not self.repo.request_exists(request_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

        item = self.repo.get_request_item_by_id(request_id, item_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request item not found")

        payload = data.model_dump(exclude_unset=True)

        nomenclature_id = payload.get("nomenclature_id")
        if nomenclature_id:
            nomenclature = self.repo.get_nomenclature_by_id(nomenclature_id)
            if not nomenclature:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Nomenclature not found",
                )

        for key, value in payload.items():
            setattr(item, key, value)

        updated = self.repo.save_request_item(item)
        return self._to_response(updated)

    @staticmethod
    def _to_response(item):
        return {
            "id": item.id,
            "request_id": item.request_id,
            "num": item.num,
            "nomenclature_id": item.nomenclature_id,
            "name": item.name,
            "unit_id": item.unit_id,
            "quantity": item.quantity,
            "warehouse_category_id": item.warehouse_category_id,
            "comment": item.comment,
        }
