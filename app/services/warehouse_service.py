from datetime import datetime
from collections import defaultdict

from fastapi import HTTPException, status
from sqlalchemy import func

from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.models.warehouse import (
    WarehouseCreate,
    WarehouseListCreate,
    WarehouseListUpdate,
    WarehouseTransferRequest,
    WarehouseUpdate,
)
from app.repositories.warehouse_repository import WarehouseRepository
from app.services.project_name_builder import load_project_reference_maps

TYPE_NAMES = {
    "warehouse": "объектный",
    "on-site warehouse": "приобъектный",
    "user": "пользовательский",
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

    def create(self, payload: WarehouseCreate, user_id: str | None = None):
        data = payload.model_dump(exclude_unset=True)
        data.pop("user_id", None)
        if user_id:
            data["created_by"] = user_id
            data["user_id"] = payload.user_id or user_id
            data["created_at"] = datetime.now()
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

    def cancel_transfer(self, receipt, items):
        source_wh_id = receipt.warehouse_id
        dest_wh_id = receipt.warehouse_transfer_id

        if not dest_wh_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Transfer destination not set")

        source_wh = self.repo.get_by_id(source_wh_id)
        if not source_wh:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source warehouse not found")
        dest_wh = self.repo.get_by_id(dest_wh_id)
        if not dest_wh:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destination warehouse not found")

        result = []
        for item in items:
            dest_rows = self.repo.get_list_rows_by_warehouse_and_nomenclature(
                dest_wh_id, item.nomenclature_id
            )
            if not dest_rows:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Nomenclature {item.nomenclature_id} not found in destination warehouse",
                )

            total_available = sum(r.quantity for r in dest_rows)
            if total_available < item.quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient quantity in destination for nomenclature {item.nomenclature_id}: available {total_available}, requested {item.quantity}",
                )

            remaining = item.quantity
            last_dest = None
            for dest_row in dest_rows:
                if remaining <= 0:
                    break
                take = min(dest_row.quantity, remaining)
                dest_row.quantity -= take
                remaining -= take
                last_dest = dest_row
                if dest_row.quantity == 0:
                    self.repo.delete_list_row(dest_row)
                else:
                    self.repo.save_list_row(dest_row)

            src_row = self.repo.find_list_row_by_details(
                warehouse_id=source_wh_id,
                nomenclature_id=item.nomenclature_id,
                price=last_dest.price,
                vat_rate=last_dest.vat_rate,
                object_levels_id=last_dest.object_levels_id,
                object_id=last_dest.object_id,
                delivery_id=last_dest.delivery_id,
                toll=last_dest.toll,
                toll_company_id=last_dest.toll_company_id,
                attribute=last_dest.attribute,
            )
            if src_row:
                src_row.quantity += item.quantity
                self.repo.save_list_row(src_row)
            else:
                src_data = {
                    "warehouse_id": source_wh_id,
                    "nomenclature_id": item.nomenclature_id,
                    "quantity": item.quantity,
                    "price": last_dest.price,
                    "vat_rate": last_dest.vat_rate,
                    "upd_item_mapping_id": last_dest.upd_item_mapping_id,
                    "attribute": last_dest.attribute,
                    "date": last_dest.date,
                    "object_levels_id": last_dest.object_levels_id,
                    "object_id": last_dest.object_id,
                    "delivery_id": last_dest.delivery_id,
                    "warehouse_receipt_id": last_dest.warehouse_receipt_id,
                    "toll": last_dest.toll,
                    "toll_company_id": last_dest.toll_company_id,
                }
                src_row = self.repo.create_list_row(src_data)

            result.append({
                "nomenclature_id": item.nomenclature_id,
                "quantity": item.quantity,
                "from_row_id": src_row.id,
            })

        return result

    def transfer_items(self, payload: WarehouseTransferRequest):
        from_wh = self.repo.get_by_id(payload.from_warehouse_id)
        if not from_wh:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source warehouse not found")
        to_wh = self.repo.get_by_id(payload.to_warehouse_id)
        if not to_wh:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destination warehouse not found")

        result = []
        for item in payload.items:
            src_rows = self.repo.get_list_rows_by_warehouse_and_nomenclature(
                payload.from_warehouse_id, item.nomenclature_id
            )
            if not src_rows:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Nomenclature {item.nomenclature_id} not found in source warehouse",
                )

            if payload.object_id:
                src_rows = [r for r in src_rows if r.object_id == payload.object_id]

            if not src_rows:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Nomenclature {item.nomenclature_id} not found for object {payload.object_id} in source warehouse",
                )

            total_available = sum(r.quantity for r in src_rows)
            if total_available < item.quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient quantity for nomenclature {item.nomenclature_id}: available {total_available}, requested {item.quantity}",
                )

            remaining = item.quantity
            last_src = None
            for src_row in src_rows:
                if remaining <= 0:
                    break
                take = min(src_row.quantity, remaining)
                src_row.quantity -= take
                remaining -= take
                last_src = src_row
                if src_row.quantity == 0:
                    self.repo.delete_list_row(src_row)
                else:
                    self.repo.save_list_row(src_row)

            dst_row = self.repo.find_list_row_by_details(
                warehouse_id=payload.to_warehouse_id,
                nomenclature_id=item.nomenclature_id,
                price=last_src.price,
                vat_rate=last_src.vat_rate,
                object_levels_id=last_src.object_levels_id,
                object_id=last_src.object_id,
                delivery_id=last_src.delivery_id,
                toll=last_src.toll,
                toll_company_id=last_src.toll_company_id,
                attribute=last_src.attribute,
            )
            if dst_row:
                dst_row.quantity += item.quantity
                self.repo.save_list_row(dst_row)
            else:
                dst_data = {
                    "warehouse_id": payload.to_warehouse_id,
                    "nomenclature_id": item.nomenclature_id,
                    "quantity": item.quantity,
                    "price": last_src.price,
                    "vat_rate": last_src.vat_rate,
                    "upd_item_mapping_id": last_src.upd_item_mapping_id,
                    "attribute": last_src.attribute,
                    "date": last_src.date,
                    "object_levels_id": last_src.object_levels_id,
                    "object_id": last_src.object_id,
                    "delivery_id": last_src.delivery_id,
                    "warehouse_receipt_id": last_src.warehouse_receipt_id,
                    "toll": last_src.toll,
                    "toll_company_id": last_src.toll_company_id,
                }
                dst_row = self.repo.create_list_row(dst_data)

            result.append({
                "nomenclature_id": item.nomenclature_id,
                "quantity": item.quantity,
                "to_row_id": dst_row.id,
            })

        return result

    def get_warehouse_list(self, warehouse_id: str, user_id: str | None = None):
        warehouse = self.repo.get_by_id(warehouse_id)
        if not warehouse:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse not found")

        rows = self.repo.get_list_by_warehouse_id(warehouse_id)
        return self._build_warehouse_list_response(warehouse, rows, user_id=user_id)

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

    def _build_warehouse_list_response(self, warehouse, rows, user_id: str | None = None):
        if not rows:
            return {
                "warehouse": self._to_response(warehouse),
                "items": [],
            }

        return {
            "warehouse": self._to_response(warehouse),
            "items": self._serialize_warehouse_list_rows(warehouse, rows, user_id=user_id),
        }

    def _serialize_warehouse_list_rows(self, warehouse, rows, user_id: str | None = None):
        return self._serialize_multi_warehouse_list_rows(rows, warehouses_by_id={warehouse.id: warehouse}, user_id=user_id)

    def _serialize_multi_warehouse_list_rows(self, rows, warehouses_by_id=None, user_id: str | None = None):
        if not rows:
            return []

        warehouses_by_id = warehouses_by_id or {
            row.id: row for row in self.repo.get_all()
        }

        nomenclature_rows = self.repo.get_nomenclature_by_ids([row.nomenclature_id for row in rows])
        nomenclature_by_id = {row.id: row for row in nomenclature_rows}

        similar_map: dict[str, int] = {}
        if user_id:
            from app.models.supply_request import NomenclatureUserSimilar
            user_rows = (
                self.repo.db.query(NomenclatureUserSimilar)
                .filter(NomenclatureUserSimilar.user_id == user_id)
                .all()
            )
            similar_map = {r.nomenclature_id: r.id for r in user_rows}

        from app.models.supply_request import NomenclatureAgreement
        nomenclature_ids = [r.id for r in nomenclature_rows]
        agreements = (
            self.repo.db.query(NomenclatureAgreement)
            .filter(NomenclatureAgreement.nomenclature_id.in_(nomenclature_ids))
            .all()
        )
        approved: set[str] = set()
        agreed: set[str] = set()
        for a in agreements:
            if a.agreement:
                if a.type == "magazine":
                    approved.add(a.nomenclature_id)
                elif a.type == "director":
                    agreed.add(a.nomenclature_id)

        from app.models.supply_request import NomenclatureFeedback
        rating_rows = (
            self.repo.db.query(
                NomenclatureFeedback.nomenclature_id,
                func.round(func.avg(NomenclatureFeedback.star), 1).label("rating"),
                func.count(NomenclatureFeedback.id).label("feedback_count"),
            )
            .filter(NomenclatureFeedback.nomenclature_id.in_(nomenclature_ids))
            .group_by(NomenclatureFeedback.nomenclature_id)
            .all()
        )
        rating_map: dict[str, float] = {r.nomenclature_id: r.rating for r in rating_rows}
        feedback_count_map: dict[str, int] = {r.nomenclature_id: r.feedback_count for r in rating_rows}

        units = self.repo.get_units_by_ids(
            [row.unit_id for row in nomenclature_rows if row.unit_id]
        )
        units_by_id = {row.id: row for row in units}

        from app.models.supply_request import WarehouseCategoryRef
        category_ids = [row.warehouse_category_id for row in nomenclature_rows if row.warehouse_category_id]
        category_rows = self.repo.db.query(WarehouseCategoryRef).filter(WarehouseCategoryRef.id.in_(category_ids)).all() if category_ids else []
        categories_by_id = {c.id: c for c in category_rows}

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
                    "nomenclature_article": nomenclature.article if nomenclature else None,
                    "warehouse_category": None
                    if not nomenclature or not nomenclature.warehouse_category_id or not categories_by_id.get(nomenclature.warehouse_category_id)
                    else {
                        "id": categories_by_id[nomenclature.warehouse_category_id].id,
                        "name": categories_by_id[nomenclature.warehouse_category_id].name,
                        "parent_id": categories_by_id[nomenclature.warehouse_category_id].parent_id,
                    },
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
                    "similar": similar_map.get(nomenclature_id) is not None,
                    "nomenclature_user_similar_id": similar_map.get(nomenclature_id),
                    "price_approved": nomenclature_id in approved,
                    "price_agreed": nomenclature_id in agreed,
                    "rating": rating_map.get(nomenclature_id),
                    "feedback_count": feedback_count_map.get(nomenclature_id, 0),
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
            "user_id": row.user_id,
            "created_by": row.created_by,
            "created_at": row.created_at,
            "toll": getattr(row, "toll", False),
            "toll_company_id": getattr(row, "toll_company_id", None),
        }
