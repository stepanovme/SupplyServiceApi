from fastapi import HTTPException, status

from app.models.delivery import (
    DeliveryCreate,
    DeliveryItemCreate,
    DeliveryItemUpdate,
    DeliveryUpdate,
)
from app.models.invoice import Invoice
from app.models.supply_request import SupplyRequest
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
        counterparty_logos = self.reference_repo.get_counterparty_logos(carrier_ids)

        invoice_ids = [row.invoice_id for row in rows if row.invoice_id]
        invoice_map = {}
        if invoice_ids:
            invoices = self.repo.db.query(Invoice).filter(Invoice.id.in_(invoice_ids)).all()
            invoice_map = {inv.id: inv for inv in invoices}
        provider_ids = list({inv.provider_id for inv in invoice_map.values() if inv.provider_id})
        provider_names = self.reference_repo.get_counterparty_names(provider_ids) if provider_ids else {}
        provider_logos = self.reference_repo.get_counterparty_logos(provider_ids) if provider_ids else {}

        request_ids = [row.request_id for row in rows if row.request_id]
        request_map = {}
        if request_ids:
            requests = self.repo.db.query(SupplyRequest).filter(SupplyRequest.id.in_(request_ids)).all()
            request_map = {req.id: req for req in requests}

        object_level_ids = set()
        for inv in invoice_map.values():
            if inv.object_levels_id:
                object_level_ids.add(inv.object_levels_id)
        for req in request_map.values():
            if req.object_levels_id:
                object_level_ids.add(req.object_levels_id)
        level_to_object_name = {}
        if object_level_ids:
            ids_list = list(object_level_ids)
            levels = self.reference_repo.get_levels_by_ids(ids_list)
            level_map = {lvl.id: lvl for lvl in levels}
            parent_object_ids = list({lvl.object_id for lvl in levels if lvl.object_id})
            direct_objects = self.reference_repo.get_objects_by_ids(ids_list)
            direct_obj_names = {o.id: (o.short_name or o.full_name or None) for o in direct_objects}
            parent_obj_names = {}
            if parent_object_ids:
                parent_objects = self.reference_repo.get_objects_by_ids(parent_object_ids)
                parent_obj_names = {o.id: (o.short_name or o.full_name or None) for o in parent_objects}
            for lid in object_level_ids:
                lvl = level_map.get(lid)
                if lvl and lvl.object_id:
                    level_to_object_name[lid] = parent_obj_names.get(lvl.object_id)
                if not level_to_object_name.get(lid):
                    level_to_object_name[lid] = direct_obj_names.get(lid)

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

        delivery_ids = [row.id for row in rows]
        all_items = {}
        all_mappings = {}
        if delivery_ids:
            items = self.repo.get_items(delivery_ids[0]) if len(delivery_ids) == 1 else []
            for did in delivery_ids:
                di = self.repo.get_items(did)
                all_items[did] = di
            mappings = self.repo.get_mappings_by_delivery_ids(delivery_ids)
            for m in mappings:
                all_mappings.setdefault(m.delivery_id, []).append(m)

        delivery_summaries = {}
        for did in delivery_ids:
            items_list = all_items.get(did, [])
            mappings_list = all_mappings.get(did, [])
            total_quantity = sum(item.quantity or 0 for item in items_list)
            received_quantity = sum(m.delivery_quantity or 0 for m in mappings_list)
            remaining_quantity = total_quantity - received_quantity
            total_items = len(items_list)
            completed_items = 0
            for item in items_list:
                item_mappings = [m for m in mappings_list if m.delivery_item_id == item.id]
                item_received = sum(m.delivery_quantity or 0 for m in item_mappings)
                if item.quantity and item_received >= item.quantity:
                    completed_items += 1
            remaining_items = total_items - completed_items
            delivery_summaries[did] = {
                "total_quantity": total_quantity,
                "received_quantity": received_quantity,
                "remaining_quantity": remaining_quantity,
                "total_items": total_items,
                "completed_items": completed_items,
                "remaining_items": remaining_items,
            }

        return [
            {
                "id": row.id,
                "num": row.num,
                "request_id": row.request_id,
                "request_name": request_map[row.request_id].name if row.request_id and row.request_id in request_map else None,
                "invoice_id": row.invoice_id,
                "invoice_name": f"{invoice_map[row.invoice_id].num} от {invoice_map[row.invoice_id].date.strftime('%d.%m.%Y')}" if row.invoice_id and row.invoice_id in invoice_map and invoice_map[row.invoice_id].num else None,
                "invoice_date": invoice_map[row.invoice_id].date.isoformat() if row.invoice_id and row.invoice_id in invoice_map and invoice_map[row.invoice_id].date else None,
                "carrier_id": row.carrier_id,
                "carrier_name": counterparty_names.get(row.carrier_id),
                "carrier_logo_url": counterparty_logos.get(row.carrier_id),
                "invoice_provider_id": invoice_map.get(row.invoice_id, None) and invoice_map[row.invoice_id].provider_id,
                "invoice_provider_name": provider_names.get(invoice_map.get(row.invoice_id, None) and invoice_map[row.invoice_id].provider_id),
                "invoice_provider_logo_url": provider_logos.get(invoice_map.get(row.invoice_id, None) and invoice_map[row.invoice_id].provider_id),
                "object_id": self._get_object_id_from_delivery(row, invoice_map, request_map),
                "object_name": self._get_object_name_from_delivery(row, invoice_map, request_map, level_to_object_name),
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
                "summary": delivery_summaries.get(row.id, {}),
                "items": self._serialize_items(self.repo.get_items(row.id), all_mappings.get(row.id, [])),
            }
            for row in rows
        ]

    def _get_object_id_from_delivery(self, row, invoice_map, request_map):
        inv = invoice_map.get(row.invoice_id)
        if inv and inv.object_levels_id:
            return inv.object_levels_id
        req = request_map.get(row.request_id)
        if req and req.object_levels_id:
            return req.object_levels_id
        return None

    def _get_object_name_from_delivery(self, row, invoice_map, request_map, level_to_object_name):
        inv = invoice_map.get(row.invoice_id)
        if inv and inv.object_levels_id:
            return level_to_object_name.get(inv.object_levels_id)
        req = request_map.get(row.request_id)
        if req and req.object_levels_id:
            return level_to_object_name.get(req.object_levels_id)
        return None

    def _serialize_items(self, rows, mappings=None):
        if not rows:
            return []
        nomenclature = self.repo.get_nomenclature([row.nomenclature_id for row in rows if row.nomenclature_id])
        user_ids = [row.created_by for row in rows if row.created_by]
        users = self.auth_user_repo.get_by_ids(list(set(user_ids)))
        users_by_id = {user.id: user for user in users}
        mappings_by_item = {}
        if mappings:
            for m in mappings:
                mappings_by_item.setdefault(m.delivery_item_id, []).append(m)
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
                "received_quantity": sum(m.delivery_quantity or 0 for m in mappings_by_item.get(row.id, [])),
                "remaining_quantity": (row.quantity or 0) - sum(m.delivery_quantity or 0 for m in mappings_by_item.get(row.id, [])),
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
