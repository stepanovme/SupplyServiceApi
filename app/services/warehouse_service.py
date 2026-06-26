from collections import defaultdict

from fastapi import HTTPException, status

from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.models.warehouse import (
    WarehouseCreate,
    WarehouseListCreate,
    WarehouseListUpdate,
    WarehouseUpdate,
)
from app.repositories.warehouse_repository import WarehouseRepository
from app.services.project_name_builder import load_project_reference_maps

TYPE_NAMES = {
    "warehouse": "объектный",
    "on-site warehouse": "приобъектный",
}


class WarehouseService:
    def __init__(
        self,
        repo: WarehouseRepository,
        reference_repo: ReferenceObjectRepository | None = None,
    ) -> None:
        self.repo = repo
        self.reference_repo = reference_repo

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

    def get_warehouse_list(self, warehouse_id: str):
        warehouse = self.repo.get_by_id(warehouse_id)
        if not warehouse:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse not found")

        rows = self.repo.get_list_by_warehouse_id(warehouse_id)
        return self._build_warehouse_list_response(warehouse, rows)

    def get_all_warehouse_list(self, search: str | None = None):
        rows = self.repo.get_all_list_rows(search)
        if not rows:
            return []
        items = self._serialize_multi_warehouse_list_rows(rows)
        grouped = defaultdict(list)
        for item in items:
            grouped[item["warehouse_id"]].append(item)

        warehouses_by_id = {row.id: row for row in self.repo.get_all()}
        return [
            {
                "warehouse": self._to_response(warehouses_by_id[warehouse_id]),
                "items": grouped_items,
            }
            for warehouse_id, grouped_items in sorted(
                grouped.items(),
                key=lambda pair: warehouses_by_id[pair[0]].name if warehouses_by_id.get(pair[0]) else "",
            )
            if warehouses_by_id.get(warehouse_id)
        ]

    def create_warehouse_list_row(self, warehouse_id: str, payload: WarehouseListCreate):
        warehouse = self.repo.get_by_id(warehouse_id)
        if not warehouse:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse not found")

        data = self._normalize_warehouse_list_payload(payload.model_dump(exclude_unset=True))
        data["warehouse_id"] = warehouse_id
        created = self.repo.create_list_row(data)

        return self._serialize_warehouse_list_rows(warehouse, [created])[0]

    def update_warehouse_list_row(
        self,
        warehouse_id: str,
        row_id: str,
        payload: WarehouseListUpdate,
    ):
        warehouse = self.repo.get_by_id(warehouse_id)
        if not warehouse:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse not found")

        row = self.repo.get_list_row_by_id(warehouse_id, row_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse list row not found")

        data = self._normalize_warehouse_list_payload(payload.model_dump(exclude_unset=True))
        for key, value in data.items():
            setattr(row, key, value)

        updated = self.repo.save_list_row(row)
        return self._serialize_warehouse_list_rows(warehouse, [updated])[0]

    def delete_warehouse_list_row(self, warehouse_id: str, row_id: str):
        warehouse = self.repo.get_by_id(warehouse_id)
        if not warehouse:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse not found")

        row = self.repo.get_list_row_by_id(warehouse_id, row_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse list row not found")

        self.repo.delete_list_row(row)
        return None

    def _build_warehouse_list_response(self, warehouse, rows):
        if not rows:
            return {
                "warehouse": self._to_response(warehouse),
                "items": [],
            }

        return {
            "warehouse": self._to_response(warehouse),
            "items": self._serialize_warehouse_list_rows(warehouse, rows),
        }

    def _serialize_warehouse_list_rows(self, warehouse, rows):
        return self._serialize_multi_warehouse_list_rows(rows, warehouses_by_id={warehouse.id: warehouse})

    def _serialize_multi_warehouse_list_rows(self, rows, warehouses_by_id=None):
        if not rows:
            return []

        warehouses_by_id = warehouses_by_id or {
            row.id: row for row in self.repo.get_all()
        }

        nomenclature_rows = self.repo.get_nomenclature_by_ids([row.nomenclature_id for row in rows])
        nomenclature_by_id = {row.id: row for row in nomenclature_rows}

        units = self.repo.get_units_by_ids(
            [row.unit_id for row in nomenclature_rows if row.unit_id]
        )
        units_by_id = {row.id: row for row in units}

        object_level_ids = [row.object_levels_id for row in rows if row.object_levels_id]
        direct_object_ids = [row.object_id for row in rows if row.object_id]
        toll_company_ids = [row.toll_company_id for row in rows if getattr(row, "toll_company_id", None)]
        levels_by_id = {}
        objects_by_id = {}
        contracts_by_id = {}
        work_types_by_id = {}
        if object_level_ids and self.reference_repo:
            (
                levels_by_id,
                objects_by_id,
                contracts_by_id,
                work_types_by_id,
            ) = load_project_reference_maps(self.reference_repo, object_level_ids)
        if direct_object_ids and self.reference_repo:
            direct_objects = self.reference_repo.get_objects_by_ids(direct_object_ids)
            for item in direct_objects:
                objects_by_id[item.id] = item
        counterparty_names = self.reference_repo.get_counterparty_names(toll_company_ids) if self.reference_repo else {}

        grouped_quantities = defaultdict(float)
        grouped_prices = {}
        grouped_vat_rates = defaultdict(list)
        grouped_mapping_ids = defaultdict(list)
        grouped_attributes = defaultdict(list)
        total_quantities = defaultdict(float)
        latest_dates = {}
        grouped_ids = defaultdict(list)
        grouped_single_rows = {}
        for row in rows:
            key = (row.warehouse_id, row.nomenclature_id, row.object_levels_id, row.object_id)
            grouped_quantities[key] += float(row.quantity or 0)
            total_quantities[(row.warehouse_id, row.nomenclature_id)] += float(row.quantity or 0)
            grouped_ids[key].append(row.id)
            grouped_single_rows.setdefault(key, row)
            if row.price is not None:
                grouped_prices.setdefault(key, []).append(float(row.price))
            if row.vat_rate is not None:
                grouped_vat_rates[key].append(int(row.vat_rate))
            if row.upd_item_mapping_id:
                grouped_mapping_ids[key].append(row.upd_item_mapping_id)
            if row.attribute:
                grouped_attributes[key].append(row.attribute)
            current_latest = latest_dates.get(key)
            if current_latest is None or row.date > current_latest:
                latest_dates[key] = row.date

        result = []
        sorted_keys = sorted(
            grouped_quantities.keys(),
            key=lambda item: (
                warehouses_by_id.get(item[0]).name if warehouses_by_id.get(item[0]) else "",
                nomenclature_by_id.get(item[1]).name if nomenclature_by_id.get(item[1]) else "",
                item[2] or "",
                item[3] or "",
            ),
        )
        for warehouse_id, nomenclature_id, object_levels_id, object_id in sorted_keys:
            warehouse = warehouses_by_id.get(warehouse_id)
            nomenclature = nomenclature_by_id.get(nomenclature_id)
            unit = units_by_id.get(nomenclature.unit_id) if nomenclature and nomenclature.unit_id else None
            project_name = None
            resolved_object_id = object_id
            if object_levels_id and self.reference_repo:
                level = levels_by_id.get(object_levels_id)
                if level:
                    resolved_object_id = level.object_id
                    ref_object = objects_by_id.get(level.object_id)
                    if ref_object:
                        project_name = ref_object.short_name or ref_object.full_name
            elif object_id and self.reference_repo:
                ref_object = objects_by_id.get(object_id)
                if ref_object:
                    project_name = ref_object.short_name or ref_object.full_name
            source_row = grouped_single_rows[(warehouse_id, nomenclature_id, object_levels_id, object_id)]
            result.append(
                {
                    "id": grouped_ids[(warehouse_id, nomenclature_id, object_levels_id, object_id)][0]
                    if len(grouped_ids[(warehouse_id, nomenclature_id, object_levels_id, object_id)]) == 1
                    else None,
                    "row_ids": grouped_ids[(warehouse_id, nomenclature_id, object_levels_id, object_id)],
                    "warehouse_id": warehouse_id,
                    "warehouse_name": warehouse.name if warehouse else None,
                    "nomenclature_id": nomenclature_id,
                    "nomenclature_name": nomenclature.name if nomenclature else None,
                    "unit_id": nomenclature.unit_id if nomenclature else None,
                    "unit_name": unit.name if unit else None,
                    "object_levels_id": object_levels_id,
                    "object_id": resolved_object_id,
                    "project_name": project_name,
                    "delivery_id": source_row.delivery_id
                    if len(grouped_ids[(warehouse_id, nomenclature_id, object_levels_id, object_id)]) == 1
                    else None,
                    "warehouse_receipt_id": source_row.warehouse_receipt_id
                    if len(grouped_ids[(warehouse_id, nomenclature_id, object_levels_id, object_id)]) == 1
                    else None,
                    "toll": source_row.toll,
                    "toll_company_id": source_row.toll_company_id,
                    "toll_company_name": counterparty_names.get(source_row.toll_company_id),
                    "quantity": round(grouped_quantities[(warehouse_id, nomenclature_id, object_levels_id, object_id)], 8),
                    "price": grouped_prices.get((warehouse_id, nomenclature_id, object_levels_id, object_id), [None])[0],
                    "vat_rate": grouped_vat_rates.get((warehouse_id, nomenclature_id, object_levels_id, object_id), [None])[0],
                    "upd_item_mapping_id": grouped_mapping_ids.get((warehouse_id, nomenclature_id, object_levels_id, object_id), [None])[0],
                    "attribute": grouped_attributes.get((warehouse_id, nomenclature_id, object_levels_id, object_id), [None])[0],
                    "total_quantity": round(total_quantities[(warehouse_id, nomenclature_id)], 8),
                    "date": latest_dates.get((warehouse_id, nomenclature_id, object_levels_id, object_id)),
                }
            )

        return result

    @staticmethod
    def _normalize_warehouse_list_payload(data: dict) -> dict:
        normalized = dict(data)
        for field_name in ("object_levels_id", "object_id", "delivery_id", "warehouse_receipt_id", "upd_item_mapping_id", "attribute", "toll_company_id"):
            if normalized.get(field_name) == "":
                normalized[field_name] = None
        if "toll" in normalized and normalized["toll"] is None:
            normalized["toll"] = False
        return normalized

    @staticmethod
    def _to_response(row):
        return {
            "id": row.id,
            "name": row.name,
            "type": row.type,
            "type_name": TYPE_NAMES.get(row.type),
            "object_levels_id": row.object_levels_id,
            "toll": getattr(row, "toll", False),
            "toll_company_id": getattr(row, "toll_company_id", None),
        }
