import json

from fastapi import HTTPException, status

from app.models.supply_request import RequestItemCreate, RequestItemUpdate
from app.repositories.request_repository import RequestRepository


class RequestItemService:
    def __init__(self, repo: RequestRepository) -> None:
        self.repo = repo

    def _is_submitted(self, request_id: int) -> bool:
        return len(self.repo.get_request_logs_by_request(request_id)) > 0

    def create(self, request_id: int, data: RequestItemCreate, user_id: str | None = None):
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

        submitted = self._is_submitted(request_id)
        if submitted:
            payload["is_new"] = True

        created = self.repo.create_request_item(request_id, payload)

        if submitted and user_id:
            self.repo.create_event_log(
                request_id=request_id,
                user_id=user_id,
                event_type="item_added",
                description=f"Добавлена позиция: {created.name or created.id}",
                metadata_json=json.dumps({
                    "item_id": created.id,
                    "name": created.name,
                    "quantity": created.quantity,
                    "is_new": True,
                }),
            )

        return self._to_response(created)

    def update(self, request_id: int, item_id: str, data: RequestItemUpdate, user_id: str | None = None):
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

        submitted = self._is_submitted(request_id)
        quantity_changed = "quantity" in payload and payload["quantity"] != item.quantity

        if submitted and quantity_changed and user_id:
            old_qty = float(item.quantity)
            new_qty = float(payload["quantity"])
            diff = new_qty - old_qty

            existing_snapshot = self.repo.get_snapshot_by_item(item_id)
            if existing_snapshot:
                snapshot_original = existing_snapshot.original_quantity
            else:
                snapshot_original = old_qty

            self.repo.create_snapshot(
                request_id=request_id,
                request_item_id=item_id,
                original_quantity=snapshot_original,
                snapshot_quantity=new_qty,
                quantity_diff=diff,
                created_by=user_id,
            )

            self.repo.create_event_log(
                request_id=request_id,
                user_id=user_id,
                event_type="quantity_changed",
                description=f"Изменено количество позиции «{item.name or item.id}»: {old_qty} → {new_qty} ({'+' if diff > 0 else ''}{diff})",
                metadata_json=json.dumps({
                    "item_id": item_id,
                    "name": item.name,
                    "old_quantity": old_qty,
                    "new_quantity": new_qty,
                    "diff": diff,
                }),
            )

        for key, value in payload.items():
            setattr(item, key, value)

        updated = self.repo.save_request_item(item)

        if submitted and not quantity_changed and user_id and payload:
            changed_fields = list(payload.keys())
            self.repo.create_event_log(
                request_id=request_id,
                user_id=user_id,
                event_type="item_updated",
                description=f"Обновлена позиция «{item.name or item.id}»: изменены поля {', '.join(changed_fields)}",
                metadata_json=json.dumps({
                    "item_id": item_id,
                    "changed_fields": changed_fields,
                }),
            )

        return self._to_response(updated)

    def delete(self, request_id: int, item_id: str, user_id: str | None = None):
        if not self.repo.request_exists(request_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

        item = self.repo.get_request_item_by_id(request_id, item_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request item not found")

        submitted = self._is_submitted(request_id)

        if submitted and user_id:
            self.repo.create_event_log(
                request_id=request_id,
                user_id=user_id,
                event_type="item_deleted",
                description=f"Удалена позиция: {item.name or item.id}",
                metadata_json=json.dumps({
                    "item_id": item_id,
                    "name": item.name,
                    "quantity": item.quantity,
                }),
            )

        self.repo.delete_request_item(item)
        return None

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
            "is_new": getattr(item, "is_new", False),
        }
