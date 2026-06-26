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


OSN_TAX_REGIME = "18e8bdb8-6795-47d7-b7c5-960daab2ba56"
USN_MINUS_TAX_REGIME = "b53c259a-10a1-11f1-aa8c-bc241127d0bd"
USN_AGENT_TAX_REGIME = "76ae3b05-ad72-400f-b41a-fa8e0ed5f0c8"


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
                "date": deal.date,
                "date_event": deal.date_event,
                "date_completed": deal.date_completed,
                "payment_mode": deal.payment_mode,
                "taxes": deal.taxes,
                "sum_deal": (
                    sum((p.price or 0) * (p.quantity or 0) for p in products_by_deal.get(deal.id, []))
                    + sum((d.price or 0) for d in deliveries_by_deal.get(deal.id, []))
                    + sum((s.price or 0) * (s.quantity or 0) for s in services_by_deal.get(deal.id, []))
                ),
                "subtotal": self._calc_subtotal(
                    products_by_deal.get(deal.id, []),
                    deliveries_by_deal.get(deal.id, []),
                    services_by_deal.get(deal.id, []),
                ),
                "total_purchase": self._calc_total_purchase(
                    products_by_deal.get(deal.id, []),
                    deliveries_by_deal.get(deal.id, []),
                    services_by_deal.get(deal.id, []),
                ),
                "acquiring": self._calc_acquiring(
                    deal.payment_mode,
                    products_by_deal.get(deal.id, []),
                    deliveries_by_deal.get(deal.id, []),
                    services_by_deal.get(deal.id, []),
                ),
                "total_tax": self._calc_total_tax(
                    deal.counterparties_from,
                    deal.taxes,
                    products_by_deal.get(deal.id, []),
                    deliveries_by_deal.get(deal.id, []),
                    services_by_deal.get(deal.id, []),
                )["total"],
                "tax_details": self._calc_total_tax(
                    deal.counterparties_from,
                    deal.taxes,
                    products_by_deal.get(deal.id, []),
                    deliveries_by_deal.get(deal.id, []),
                    services_by_deal.get(deal.id, []),
                ),
                "net_profit": self._calc_net_profit(
                    deal.counterparties_from,
                    deal.payment_mode,
                    deal.taxes,
                    products_by_deal.get(deal.id, []),
                    deliveries_by_deal.get(deal.id, []),
                    services_by_deal.get(deal.id, []),
                ),
                "created_at": deal.created_at,
                "created_by": deal.created_by,
                "created_by_user": self._map_user(users_by_id.get(deal.created_by)),
                "deliveries": [self._serialize_delivery(item) for item in deliveries_by_deal.get(deal.id, [])],
                "products": serialized_products_by_deal.get(deal.id, []),
                "services": [self._serialize_service(item) for item in services_by_deal.get(deal.id, [])],
            }
            for deal in deals
        ]

    @staticmethod
    def _calc_subtotal(products, deliveries, services) -> float:
        return (
            sum((p.price or 0) * (p.quantity or 0) for p in products)
            + sum((d.price or 0) for d in deliveries)
            + sum((s.price or 0) * (s.quantity or 0) for s in services)
        )

    @staticmethod
    def _calc_total_purchase(products, deliveries, services) -> float:
        return (
            sum((p.price_purchase or 0) * (p.quantity or 0) for p in products)
            + sum((d.price_purchase or 0) for d in deliveries)
            + sum((s.price_purchase or 0) * (s.quantity or 0) for s in services)
        )

    @staticmethod
    def _calc_acquiring(payment_mode, products, deliveries, services) -> float:
        if payment_mode != "non-cash":
            return 0.0
        subtotal = (
            sum((p.price or 0) * (p.quantity or 0) for p in products)
            + sum((d.price or 0) for d in deliveries)
            + sum((s.price or 0) * (s.quantity or 0) for s in services)
        )
        return round(subtotal * 0.012, 2)

    @staticmethod
    def _calc_total_tax(tax_regime_id: str | None, taxes: str | None, products, deliveries, services) -> dict:
        subtotal = DealServiceManager._calc_subtotal(products, deliveries, services)
        total_purchase = DealServiceManager._calc_total_purchase(products, deliveries, services)
        result: dict = {}

        if tax_regime_id == OSN_TAX_REGIME:
            goods_no_vat = sum(
                (p.price or 0) * (p.quantity or 0)
                for p in products
                if p.vat_rate not in (20, 22)
            )
            services_sum = sum((s.price or 0) * (s.quantity or 0) for s in services)
            vat_goods = round(goods_no_vat * 0.22, 2)
            vat_services = round(services_sum * 0.22, 2)
            result = {
                "vat_goods_22": vat_goods,
                "vat_services_22": vat_services,
            }

        elif tax_regime_id == USN_MINUS_TAX_REGIME:
            usn = round(max(subtotal - total_purchase, 0) * 0.15, 2)
            nds = round(subtotal * 0.05, 2)
            result = {
                "usn_15": usn,
                "nds_5": nds,
            }

        elif tax_regime_id == USN_AGENT_TAX_REGIME:
            if taxes == "agreement":
                base = subtotal * 0.10
            else:
                base = subtotal
            usn_6 = round(base * 0.06, 2)
            pfr_1 = round(base * 0.01, 2)
            result = {
                "usn_6": usn_6,
                "pfr_1": pfr_1,
                "base": round(base, 2),
            }

        result["total"] = round(sum(v for k, v in result.items() if k != "base"), 2)
        return result

    @staticmethod
    def _calc_net_profit(tax_regime_id: str | None, payment_mode: str | None, taxes: str | None, products, deliveries, services) -> float:
        subtotal = DealServiceManager._calc_subtotal(products, deliveries, services)
        total_purchase = DealServiceManager._calc_total_purchase(products, deliveries, services)
        total_tax = DealServiceManager._calc_total_tax(tax_regime_id, taxes, products, deliveries, services)["total"]
        acquiring = DealServiceManager._calc_acquiring(payment_mode or "cash", products, deliveries, services)
        return round(subtotal - total_purchase - total_tax - acquiring, 2)

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
        for field_name in ("payment_mode", "taxes"):
            if field_name in normalized and normalized[field_name] == "":
                normalized.pop(field_name, None)
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
