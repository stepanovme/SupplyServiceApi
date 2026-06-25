from fastapi import HTTPException, status

from app.models.delivery import (
    DeliveryCreate,
    DeliveryItemCreate,
    DeliveryItemUpdate,
    DeliveryUpdate,
)
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.counterparty_repository import CounterpartyRepository
from app.repositories.delivery_repository import DeliveryRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository

DEFAULT_DELIVERY_STATUS_ID = "1ff33333-1312-11f1-aa8c-bc241127d0bd"


class DeliveryService:
    def __init__(
        self,
        repo: DeliveryRepository,
        counterparty_repo: CounterpartyRepository,
        auth_user_repo: AuthUserRepository,
        reference_repo: ReferenceObjectRepository,
    ) -> None:
        self.repo = repo
        self.counterparty_repo = counterparty_repo
        self.auth_user_repo = auth_user_repo
        self.reference_repo = reference_repo

    def get_deliveries(
        self,
        delivery_from: str | None = None,
        delivery_to: str | None = None,
    ):
        return self._serialize_deliveries(
            self.repo.get_all(delivery_from=delivery_from, delivery_to=delivery_to)
        )

    def get_delivery(self, delivery_id: str):
        row = self.repo.get_by_id(delivery_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery not found")
        return self._serialize_deliveries([row])[0]

    def create_delivery(self, payload: DeliveryCreate, user_id: str):
        data = self._normalize_delivery_payload(payload.model_dump(exclude_unset=True))
        data.setdefault("num", self.repo.get_next_num())
        data.setdefault("status_id", DEFAULT_DELIVERY_STATUS_ID)
        data["created_by"] = user_id
        created = self.repo.create(data)
        return self.get_delivery(created.id)

    def update_delivery(self, delivery_id: str, payload: DeliveryUpdate):
        row = self.repo.get_by_id(delivery_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery not found")
        for key, value in self._normalize_delivery_payload(payload.model_dump(exclude_unset=True)).items():
            setattr(row, key, value)
        self.repo.save(row)
        return self.get_delivery(delivery_id)

    def delete_delivery(self, delivery_id: str):
        row = self.repo.get_by_id(delivery_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery not found")
        self.repo.delete(row)
        return None

    def get_delivery_items(self, delivery_id: str):
        self._ensure_delivery_exists(delivery_id)
        rows = self.repo.get_items(delivery_id)
        return self._serialize_items(rows)

    def create_delivery_item(self, delivery_id: str, payload: DeliveryItemCreate, user_id: str):
        self._ensure_delivery_exists(delivery_id)
        data = self._normalize_delivery_item_payload(payload.model_dump(exclude_unset=True))
        data = self.repo.coerce_item_payload_to_schema(data)
        data["created_by"] = user_id
        created = self.repo.create_item(delivery_id, data)
        return self._serialize_items([created])[0]

    def update_delivery_item(self, delivery_id: str, item_id: str, payload: DeliveryItemUpdate):
        row = self.repo.get_item_by_id(delivery_id, item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery item not found")
        update_payload = self._normalize_delivery_item_payload(payload.model_dump(exclude_unset=True))
        update_payload = self.repo.coerce_item_payload_to_schema(update_payload)
        for key, value in update_payload.items():
            setattr(row, key, value)
        updated = self.repo.save_item(row)
        return self._serialize_items([updated])[0]

    def delete_delivery_item(self, delivery_id: str, item_id: str):
        row = self.repo.get_item_by_id(delivery_id, item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery item not found")
        self.repo.delete_item(row)
        return None

    def _serialize_deliveries(self, rows):
        if not rows:
            return []
        created_by_ids = [row.created_by for row in rows if row.created_by]
        driver_ids = [row.driver_id for row in rows if row.driver_id]
        users = self.auth_user_repo.get_by_ids(list({*created_by_ids, *driver_ids}))
        users_by_id = {user.id: user for user in users}
        status_names = self.repo.get_status_names([row.status_id for row in rows if row.status_id])

        carrier_ids = [row.carrier_id for row in rows if row.carrier_id]
        counterparty_names = self.reference_repo.get_counterparty_names(carrier_ids)

        warehouse_ids = []
        object_ids = []
        company_ids = []
        for row in rows:
            if row.delivery_from_type == "warehouse":
                warehouse_ids.append(row.delivery_from)
            elif row.delivery_from_type == "object":
                object_ids.append(row.delivery_from)
            elif row.delivery_from_type == "company":
                company_ids.append(row.delivery_from)
            if row.delivery_to_type == "warehouse":
                warehouse_ids.append(row.delivery_to)
            elif row.delivery_to_type == "object":
                object_ids.append(row.delivery_to)
            elif row.delivery_to_type == "company":
                company_ids.append(row.delivery_to)

        warehouses = self.repo.get_warehouses(warehouse_ids)
        object_rows = self.reference_repo.get_objects_by_ids(object_ids)
        object_names = {row.id: (row.short_name or row.full_name) for row in object_rows}
        company_names = self.reference_repo.get_counterparty_names(company_ids)

        return [
            {
                "id": row.id,
                "num": row.num,
                "request_id": row.request_id,
                "invoice_id": row.invoice_id,
                "carrier_id": row.carrier_id,
                "carrier_name": counterparty_names.get(row.carrier_id),
                "pick_up_date": row.pick_up_date,
                "pick_up_date_planned": row.pick_up_date_planned,
                "planned_delivery_from": row.planned_delivery_from,
                "planned_delivery_to": row.planned_delivery_to,
                "delivery_from": row.delivery_from,
                "delivery_from_type": row.delivery_from_type,
                "delivery_from_name": self._resolve_location_name(
                    row.delivery_from, row.delivery_from_type, warehouses, object_names, company_names
                ),
                "delivery_to": row.delivery_to,
                "delivery_to_type": row.delivery_to_type,
                "delivery_to_name": self._resolve_location_name(
                    row.delivery_to, row.delivery_to_type, warehouses, object_names, company_names
                ),
                "driver_id": row.driver_id,
                "driver_user": self._map_user(users_by_id.get(row.driver_id)),
                "status_id": row.status_id,
                "status_name": status_names.get(row.status_id),
                "comment": row.comment,
                "created_at": row.created_at,
                "created_by": row.created_by,
                "created_by_user": self._map_user(users_by_id.get(row.created_by)),
                "items": self._serialize_items(self.repo.get_items(row.id)),
            }
            for row in rows
        ]

    def _serialize_items(self, rows):
        if not rows:
            return []
        nomenclature = self.repo.get_nomenclature([row.nomenclature_id for row in rows if row.nomenclature_id])
        user_ids = [row.created_by for row in rows if row.created_by]
        users = self.auth_user_repo.get_by_ids(list(set(user_ids)))
        users_by_id = {user.id: user for user in users}
        return [
            {
                "id": row.id,
                "delivery_id": row.delivery_id,
                "nomenclature_id": row.nomenclature_id,
                "nomenclature_name": nomenclature.get(row.nomenclature_id).name if nomenclature.get(row.nomenclature_id) else None,
                "request_item_id": row.request_item_id,
                "invoice_item_id": row.invoice_item_id,
                "name": row.name,
                "unit_name": row.unit_name,
                "quantity": row.quantity,
                "created_at": row.created_at,
                "created_by": row.created_by,
                "created_by_user": self._map_user(users_by_id.get(row.created_by)),
            }
            for row in rows
        ]

    def _ensure_delivery_exists(self, delivery_id: str) -> None:
        if not self.repo.get_by_id(delivery_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery not found")

    @staticmethod
    def _resolve_location_name(
        value: str | None,
        value_type: str | None,
        warehouses: dict,
        object_names: dict[str, str],
        company_names: dict[str, str],
    ) -> str | None:
        if not value:
            return None
        if value_type == "warehouse":
            warehouse = warehouses.get(value)
            return warehouse.name if warehouse else None
        if value_type == "object":
            return object_names.get(value)
        if value_type == "company":
            return company_names.get(value)
        return None

    @staticmethod
    def _map_user(user):
        if not user:
            return None
        name_initial = f"{user.name[0]}." if user.name else ""
        patronymic_initial = f"{user.patronymic[0]}." if user.patronymic else ""
        short_fio = " ".join(part for part in [user.surname, name_initial, patronymic_initial] if part).strip()
        return {
            "id": user.id,
            "name": user.name,
            "surname": user.surname,
            "patronymic": user.patronymic,
            "short_fio": short_fio,
        }

    @staticmethod
    def _normalize_delivery_item_payload(data: dict) -> dict:
        normalized = dict(data)
        for field_name in ("nomenclature_id", "request_item_id", "invoice_item_id", "name", "unit_name"):
            if normalized.get(field_name) == "":
                normalized[field_name] = None
        return normalized

    @staticmethod
    def _normalize_delivery_payload(data: dict) -> dict:
        normalized = dict(data)
        for field_name in (
            "carrier_id",
            "delivery_from",
            "delivery_from_type",
            "delivery_to",
            "delivery_to_type",
            "driver_id",
            "status_id",
            "comment",
        ):
            if normalized.get(field_name) == "":
                if field_name == "status_id":
                    normalized.pop(field_name, None)
                else:
                    normalized[field_name] = None
        return normalized
