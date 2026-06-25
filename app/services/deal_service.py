import uuid

from fastapi import HTTPException, status

from app.models.deal import (
    Deal,
    DealCreate,
    DealDelivery,
    DealDeliveryCreate,
    DealDeliveryUpdate,
    DealProduct,
    DealProductCreate,
    DealProductUpdate,
    DealService,
    DealServiceCreate,
    DealServiceUpdate,
    DealUpdate,
)
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.counterparty_repository import CounterpartyRepository
from app.repositories.deal_repository import DealRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository

DEFAULT_DEAL_STATUS_ID = "662ce068-3fc1-11f1-b298-bc241127d0bd"


class DealServiceManager:
    def __init__(
        self,
        repo: DealRepository,
        counterparty_repo: CounterpartyRepository,
        reference_repo: ReferenceObjectRepository | None = None,
        auth_user_repo: AuthUserRepository | None = None,
    ) -> None:
        self.repo = repo
        self.counterparty_repo = counterparty_repo
        self.reference_repo = reference_repo
        self.auth_user_repo = auth_user_repo

    def get_deals(self):
        return self._serialize_deals(self.repo.get_all())

    def get_deal(self, deal_id: str):
        deal = self.repo.get_by_id(deal_id)
        if not deal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
        return self._serialize_deals([deal])[0]

    def create_deal(self, payload: DealCreate, user_id: str):
        data = self._normalize_deal_payload(payload.model_dump(exclude_unset=True))
        data.setdefault("status_id", DEFAULT_DEAL_STATUS_ID)
        data["created_by"] = user_id
        row = self.repo.create(Deal(id=str(uuid.uuid4()), **data))
        return self.get_deal(row.id)

    def update_deal(self, deal_id: str, payload: DealUpdate):
        row = self.repo.get_by_id(deal_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
        for key, value in self._normalize_deal_payload(payload.model_dump(exclude_unset=True)).items():
            setattr(row, key, value)
        self.repo.save(row)
        return self.get_deal(deal_id)

    def delete_deal(self, deal_id: str):
        row = self.repo.get_by_id(deal_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
        self.repo.delete(row)
        return None

    def get_deal_deliveries(self, deal_id: str):
        self._ensure_deal_exists(deal_id)
        return [self._serialize_delivery(item) for item in self.repo.get_deliveries(deal_id)]

    def create_deal_delivery(self, deal_id: str, payload: DealDeliveryCreate):
        self._ensure_deal_exists(deal_id)
        row = self.repo.create_delivery(DealDelivery(id=str(uuid.uuid4()), deal_id=deal_id, **payload.model_dump(exclude_unset=True)))
        return self._serialize_delivery(row)

    def update_deal_delivery(self, deal_id: str, delivery_id: str, payload: DealDeliveryUpdate):
        row = self.repo.get_delivery_by_id(deal_id, delivery_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal delivery not found")
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(row, key, value)
        return self._serialize_delivery(self.repo.save_delivery(row))

    def delete_deal_delivery(self, deal_id: str, delivery_id: str):
        row = self.repo.get_delivery_by_id(deal_id, delivery_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal delivery not found")
        self.repo.delete_delivery(row)
        return None

    def get_deal_products(self, deal_id: str):
        self._ensure_deal_exists(deal_id)
        return self._serialize_products(self.repo.get_products(deal_id))

    def create_deal_product(self, deal_id: str, payload: DealProductCreate):
        self._ensure_deal_exists(deal_id)
        row = self.repo.create_product(DealProduct(id=str(uuid.uuid4()), deal_id=deal_id, **payload.model_dump(exclude_unset=True)))
        return self._serialize_products([row])[0]

    def update_deal_product(self, deal_id: str, product_id: str, payload: DealProductUpdate):
        row = self.repo.get_product_by_id(deal_id, product_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal product not found")
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(row, key, value)
        return self._serialize_products([self.repo.save_product(row)])[0]

    def delete_deal_product(self, deal_id: str, product_id: str):
        row = self.repo.get_product_by_id(deal_id, product_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal product not found")
        self.repo.delete_product(row)
        return None

    def get_deal_services(self, deal_id: str):
        self._ensure_deal_exists(deal_id)
        return [self._serialize_service(item) for item in self.repo.get_services(deal_id)]

    def create_deal_service(self, deal_id: str, payload: DealServiceCreate):
        self._ensure_deal_exists(deal_id)
        row = self.repo.create_service(DealService(id=str(uuid.uuid4()), deal_id=deal_id, **payload.model_dump(exclude_unset=True)))
        return self._serialize_service(row)

    def update_deal_service(self, deal_id: str, service_id: str, payload: DealServiceUpdate):
        row = self.repo.get_service_by_id(deal_id, service_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal service not found")
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(row, key, value)
        return self._serialize_service(self.repo.save_service(row))

    def delete_deal_service(self, deal_id: str, service_id: str):
        row = self.repo.get_service_by_id(deal_id, service_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal service not found")
        self.repo.delete_service(row)
        return None

    def _ensure_deal_exists(self, deal_id: str) -> None:
        if not self.repo.get_by_id(deal_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")

    def _serialize_deals(self, deals: list[Deal]):
        if not deals:
            return []
        statuses = self.repo.get_status_names([deal.status_id for deal in deals if deal.status_id])
        counterparty_ids = [deal.counterparties_to for deal in deals if deal.counterparties_to] + [
            deal.counterparties_from for deal in deals if deal.counterparties_from
        ]
        object_ids = [deal.object_id for deal in deals if deal.object_id]
        counterparty_names = {counterparty_id: self._counterparty_name(counterparty_id) for counterparty_id in set(counterparty_ids)}
        object_names = self._get_object_names(object_ids)
        deliveries_by_deal = {deal.id: self.repo.get_deliveries(deal.id) for deal in deals}
        products_by_deal = {deal.id: self.repo.get_products(deal.id) for deal in deals}
        services_by_deal = {deal.id: self.repo.get_services(deal.id) for deal in deals}
        users_by_id = self._get_users_map([deal.created_by for deal in deals if deal.created_by])
        serialized_products_by_deal = {
            deal_id: self._serialize_products(rows)
            for deal_id, rows in products_by_deal.items()
        }
        deal_ids = [deal.id for deal in deals if deal.id]
        chat_ids_map = self.repo.get_chat_ids_by_deal(deal_ids)
        return [
            {
                "id": deal.id,
                "chat_id": chat_ids_map.get(deal.id),
                "name": deal.name,
                "object_id": deal.object_id,
                "object_name": object_names.get(deal.object_id),
                "counterparties_to": deal.counterparties_to,
                "counterparties_to_name": counterparty_names.get(deal.counterparties_to),
                "counterparties_from": deal.counterparties_from,
                "counterparties_from_name": counterparty_names.get(deal.counterparties_from),
                "status_id": deal.status_id,
                "status_name": statuses.get(deal.status_id),
                "created_at": deal.created_at,
                "created_by": deal.created_by,
                "created_by_user": self._map_user(users_by_id.get(deal.created_by)),
                "deliveries": [self._serialize_delivery(item) for item in deliveries_by_deal.get(deal.id, [])],
                "products": serialized_products_by_deal.get(deal.id, []),
                "services": [self._serialize_service(item) for item in services_by_deal.get(deal.id, [])],
            }
            for deal in deals
        ]

    def _serialize_products(self, rows: list[DealProduct]):
        nomenclature = self.repo.get_nomenclature([row.nomenclature_id for row in rows if row.nomenclature_id])
        unit_names = self.repo.get_unit_names(
            [item.unit_id for item in nomenclature.values() if getattr(item, "unit_id", None)]
        )
        warehouses = self.repo.get_warehouses([row.warehouse_id for row in rows if row.warehouse_id])
        return [
            {
                "id": row.id,
                "deal_id": row.deal_id,
                "nomenclature_id": row.nomenclature_id,
                "nomenclature_name": nomenclature.get(row.nomenclature_id).name if nomenclature.get(row.nomenclature_id) else None,
                "unit_name": (
                    unit_names.get(nomenclature.get(row.nomenclature_id).unit_id)
                    if nomenclature.get(row.nomenclature_id) and nomenclature.get(row.nomenclature_id).unit_id
                    else None
                ),
                "vat_rate": row.vat_rate,
                "warehouse_id": row.warehouse_id,
                "warehouse_name": warehouses.get(row.warehouse_id).name if warehouses.get(row.warehouse_id) else None,
                "price_purchase": row.price_purchase,
                "price": row.price,
                "quantity": row.quantity,
            }
            for row in rows
        ]

    @staticmethod
    def _serialize_delivery(row: DealDelivery):
        return {
            "id": row.id,
            "deal_id": row.deal_id,
            "type": row.type,
            "price_purchase": row.price_purchase,
            "price": row.price,
            "comment": row.comment,
        }

    @staticmethod
    def _serialize_service(row: DealService):
        return {
            "id": row.id,
            "deal_id": row.deal_id,
            "name": row.name,
            "unit_name": row.unit_name,
            "quantity": row.quantity,
            "price_purchase": row.price_purchase,
            "price": row.price,
        }

    def _counterparty_name(self, counterparty_id: str | None) -> str | None:
        payload = self.counterparty_repo.get_counterparty_brief(counterparty_id)
        return payload.get("short_name") if payload else None

    def _get_object_names(self, object_ids: list[str]) -> dict[str, str]:
        if not self.reference_repo:
            return {}
        rows = self.reference_repo.get_objects_by_ids([object_id for object_id in object_ids if object_id])
        return {row.id: (row.short_name or row.full_name) for row in rows}

    @staticmethod
    def _normalize_deal_payload(data: dict) -> dict:
        normalized = dict(data)
        nullable_fk_fields = ("object_id", "counterparties_to", "counterparties_from")
        for field_name in nullable_fk_fields:
            if field_name in normalized and normalized[field_name] == "":
                normalized[field_name] = None
        if normalized.get("status_id") == "":
            normalized.pop("status_id", None)
        return normalized

    def _get_users_map(self, user_ids: list[str]):
        if not self.auth_user_repo:
            return {}
        try:
            users = self.auth_user_repo.get_by_ids([user_id for user_id in user_ids if user_id])
        except Exception:
            return {}
        return {user.id: user for user in users}

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
