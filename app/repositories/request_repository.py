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
                }
                for log in logs_by_request_id.get(str(req.id), [])
            ]

            result.append(
                {
                    "id": req.id,
                    "object_levels_id": req.object_levels_id,
                    "name": req.name,
                    "created_by": req.created_by,
                    "executor": req.executor,
                    "created_at": req.created_at,
                    "started_at": req.started_at,
                    "approved_at": req.approved_at,
                    "completed_at": req.completed_at,
                    "deadline": req.deadline,
                    "status": None if not status else {"id": status.id, "name": status.name},
                    "items": request_items,
                    "logs": request_logs,
                }
            )

        return result
