import uuid
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.supply_request import (
    NomenclatureRef,
    RequestItem,
    RequestLog,
    StatusRef,
    SupplyRequest,
    UnitRef,
    WarehouseCategoryRef,
)


class RequestRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(self):
        requests = self.db.query(SupplyRequest).order_by(SupplyRequest.id.desc()).all()
        if not requests:
            return []

        request_ids = [req.id for req in requests]
        request_ids_str = [str(req_id) for req_id in request_ids]

        statuses = self.db.query(StatusRef).all()
        statuses_by_id = {status.id: status for status in statuses}

        items = self.db.query(RequestItem).filter(RequestItem.request_id.in_(request_ids)).all()
        items_by_request_id = defaultdict(list)
        for item in items:
            items_by_request_id[item.request_id].append(item)

        nomenclature_ids = list({item.nomenclature_id for item in items if item.nomenclature_id})
        unit_ids = {item.unit_id for item in items if item.unit_id}
        warehouse_ids = {item.warehouse_category_id for item in items if item.warehouse_category_id}

        nomenclature_rows = []
        if nomenclature_ids:
            nomenclature_rows = (
                self.db.query(NomenclatureRef)
                .filter(NomenclatureRef.id.in_(nomenclature_ids))
                .all()
            )
        nomenclature_by_id = {row.id: row for row in nomenclature_rows}
        for nomenclature in nomenclature_rows:
            if nomenclature.unit_id:
                unit_ids.add(nomenclature.unit_id)
            if nomenclature.warehouse_category_id:
                warehouse_ids.add(nomenclature.warehouse_category_id)

        unit_rows = []
        if unit_ids:
            unit_rows = self.db.query(UnitRef).filter(UnitRef.id.in_(list(unit_ids))).all()
        units_by_id = {row.id: row for row in unit_rows}

        warehouse_rows = []
        if warehouse_ids:
            warehouse_rows = (
                self.db.query(WarehouseCategoryRef)
                .filter(WarehouseCategoryRef.id.in_(list(warehouse_ids)))
                .all()
            )
        warehouse_by_id = {row.id: row for row in warehouse_rows}

        logs = self.db.query(RequestLog).filter(RequestLog.request_id.in_(request_ids_str)).all()
        logs_by_request_id = defaultdict(list)
        for log in logs:
            logs_by_request_id[log.request_id].append(log)

        result = []
        for req in requests:
            status = statuses_by_id.get(req.status_id)
            request_items = []
            for item in items_by_request_id.get(req.id, []):
                nomenclature = nomenclature_by_id.get(item.nomenclature_id)
                unit = units_by_id.get(item.unit_id)
                warehouse = warehouse_by_id.get(item.warehouse_category_id)
                nomenclature_unit = (
                    units_by_id.get(nomenclature.unit_id)
                    if nomenclature and nomenclature.unit_id
                    else None
                )
                nomenclature_warehouse = (
                    warehouse_by_id.get(nomenclature.warehouse_category_id)
                    if nomenclature and nomenclature.warehouse_category_id
                    else None
                )

                request_items.append(
                    {
                        "id": item.id,
                        "request_id": item.request_id,
                        "num": item.num,
                        "name": item.name,
                        "quantity": item.quantity,
                        "comment": item.comment,
                        "nomenclature": None
                        if not nomenclature
                        else {
                            "id": nomenclature.id,
                            "name": nomenclature.name,
                            "description": nomenclature.description,
                            "article": nomenclature.article,
                            "unit_id": nomenclature.unit_id,
                            "warehouse_category_id": nomenclature.warehouse_category_id,
                            "unit": None
                            if not nomenclature_unit
                            else {"id": nomenclature_unit.id, "name": nomenclature_unit.name},
                            "warehouse_category": None
                            if not nomenclature_warehouse
                            else {
                                "id": nomenclature_warehouse.id,
                                "name": nomenclature_warehouse.name,
                                "parent_id": nomenclature_warehouse.parent_id,
                            },
                            "length": nomenclature.length,
                            "width": nomenclature.width,
                            "height": nomenclature.height,
                            "weight": nomenclature.weight,
                        },
                        "unit": None if not unit else {"id": unit.id, "name": unit.name},
                        "warehouse_category": None
                        if not warehouse
                        else {
                            "id": warehouse.id,
                            "name": warehouse.name,
                            "parent_id": warehouse.parent_id,
                        },
                    }
                )

            request_logs = [
                {
                    "id": log.id,
                    "user_id": log.user_id,
                    "request_id": log.request_id,
                    "status_name": log.status_name,
                    "date_response": log.date_response,
                }
                for log in logs_by_request_id.get(str(req.id), [])
            ]

            result.append(
                {
                    "id": req.id,
                    "object_levels_id": req.object_levels_id,
                    "name": req.name,
                    "comment": req.comment,
                    "created_by": req.created_by,
                    "executor": req.executor,
                    "created_at": req.created_at,
                    "started_at": req.started_at,
                    "approved_at": req.approved_at,
                    "rejected_at": req.rejected_at,
                    "completed_at": req.completed_at,
                    "deadline": req.deadline,
                    "status": None if not status else {"id": status.id, "name": status.name},
                    "items": request_items,
                    "logs": request_logs,
                }
            )

        return result

    def get_model_by_id(self, request_id: int) -> SupplyRequest | None:
        return self.db.query(SupplyRequest).filter(SupplyRequest.id == request_id).first()

    def create(self, request_row: SupplyRequest) -> SupplyRequest:
        self.db.add(request_row)
        self.db.commit()
        self.db.refresh(request_row)
        return request_row

    def save(self, request_row: SupplyRequest) -> SupplyRequest:
        self.db.commit()
        self.db.refresh(request_row)
        return request_row

    def request_exists(self, request_id: int) -> bool:
        return (
            self.db.query(SupplyRequest.id).filter(SupplyRequest.id == request_id).first() is not None
        )

    def get_units_by_ids(self, unit_ids: list[str]) -> list[UnitRef]:
        unique_ids = list({item for item in unit_ids if item})
        if not unique_ids:
            return []
        return self.db.query(UnitRef).filter(UnitRef.id.in_(unique_ids)).all()

    def get_warehouse_categories_by_ids(self, category_ids: list[str]) -> list[WarehouseCategoryRef]:
        unique_ids = list({item for item in category_ids if item})
        if not unique_ids:
            return []
        return self.db.query(WarehouseCategoryRef).filter(WarehouseCategoryRef.id.in_(unique_ids)).all()

    def get_nomenclature_by_id(self, nomenclature_id: str) -> NomenclatureRef | None:
        return self.db.query(NomenclatureRef).filter(NomenclatureRef.id == nomenclature_id).first()

    def get_next_request_item_num(self, request_id: int) -> int:
        max_num = (
            self.db.query(RequestItem.num).filter(RequestItem.request_id == request_id).order_by(RequestItem.num.desc()).first()
        )
        return (max_num[0] + 1) if max_num else 1

    def create_request_item(
        self,
        request_id: int,
        payload: dict,
    ) -> RequestItem:
        item = RequestItem(
            id=str(uuid.uuid4()),
            request_id=request_id,
            **payload,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_request_item_by_id(self, request_id: int, item_id: str) -> RequestItem | None:
        return (
            self.db.query(RequestItem)
            .filter(
                RequestItem.id == item_id,
                RequestItem.request_id == request_id,
            )
            .first()
        )

    def save_request_item(self, item: RequestItem) -> RequestItem:
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete_request_item(self, item: RequestItem) -> None:
        self.db.delete(item)
        self.db.commit()

    def create_request_log(self, request_id: int, payload: dict) -> RequestLog:
        item = RequestLog(
            id=str(uuid.uuid4()),
            request_id=str(request_id),
            **payload,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_request_log_by_id(self, request_id: int, log_id: str) -> RequestLog | None:
        return (
            self.db.query(RequestLog)
            .filter(
                RequestLog.id == log_id,
                RequestLog.request_id == str(request_id),
            )
            .first()
        )

    def save_request_log(self, item: RequestLog) -> RequestLog:
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete_request_log(self, item: RequestLog) -> None:
        self.db.delete(item)
        self.db.commit()
