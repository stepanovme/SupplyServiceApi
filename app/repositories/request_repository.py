import uuid
from collections import defaultdict
from types import SimpleNamespace

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.models.item_mapping import ItemMapping
from app.models.supply_request import (
    NomenclatureRef,
    RequestItem,
    RequestLog,
    StatusRef,
    SupplyRequest,
    UnitRef,
    WarehouseCategoryRef,
)
from app.models.request_warehouse_list import RequestWarehouseList
from app.models.warehouse import Warehouse


class RequestRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._table_columns_cache: dict[str, set[str]] = {}

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

        request_warehouse_rows = self.db.query(RequestWarehouseList).filter(RequestWarehouseList.request_id.in_(request_ids)).all()
        request_warehouse_by_item_id = defaultdict(list)
        warehouse_ids_for_links = set()
        for link in request_warehouse_rows:
            request_warehouse_by_item_id[link.request_item_id].append(link)
            if link.warehouse_id:
                warehouse_ids_for_links.add(link.warehouse_id)
        warehouses_by_id = {}
        if warehouse_ids_for_links:
            warehouses = self.db.query(Warehouse).filter(Warehouse.id.in_(list(warehouse_ids_for_links))).all()
            warehouses_by_id = {row.id: row for row in warehouses}

        nomenclature_ids = list({item.nomenclature_id for item in items if item.nomenclature_id})
        unit_ids = {item.unit_id for item in items if item.unit_id}
        warehouse_ids = {item.warehouse_category_id for item in items if item.warehouse_category_id}

        nomenclature_rows = []
        if nomenclature_ids:
            nomenclature_rows = self._get_nomenclature_by_ids(nomenclature_ids)
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

        mappings = self.db.query(ItemMapping).filter(ItemMapping.request_id.in_(request_ids)).all()
        mapped_request_item_ids_by_request_id = defaultdict(set)
        for mapping in mappings:
            if mapping.request_item_id and mapping.invoice_item_id:
                mapped_request_item_ids_by_request_id[mapping.request_id].add(mapping.request_item_id)

        invoices = self.db.query(Invoice).filter(Invoice.request_id.in_(request_ids)).all()
        invoices_by_request_id = defaultdict(list)
        for invoice in invoices:
            status = statuses_by_id.get(invoice.status)
            invoices_by_request_id[invoice.request_id].append(
                {
                    "id": invoice.id,
                    "num": invoice.num,
                    "date": invoice.date,
                    "provider_id": invoice.provider_id,
                    "payer_id": invoice.payer_id,
                    "status": invoice.status,
                    "status_name": status.name if status else None,
                }
            )

        result = []
        for req in requests:
            status = statuses_by_id.get(req.status_id)
            request_items = []
            warehouse_positions_total = len(items_by_request_id.get(req.id, []))
            warehouse_positions_linked = 0
            warehouse_positions_on_stock = 0
            warehouse_positions_delivered = 0
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
                linked_rows = request_warehouse_by_item_id.get(item.id, [])
                linked_warehouses = [warehouses_by_id.get(link.warehouse_id) for link in linked_rows if warehouses_by_id.get(link.warehouse_id)]
                linked_stock = any(warehouse_row and warehouse_row.type == "warehouse" for warehouse_row in linked_warehouses)
                linked_delivered = any(warehouse_row and warehouse_row.type == "on-site warehouse" for warehouse_row in linked_warehouses)
                if linked_rows:
                    warehouse_positions_linked += 1
                if linked_stock:
                    warehouse_positions_on_stock += 1
                if linked_delivered:
                    warehouse_positions_delivered += 1
                request_quantity = sum(float(link.request_qantity or 0) for link in linked_rows) if linked_rows else None
                warehouse_quantity = sum(float(link.warehouse_quantity or 0) for link in linked_rows) if linked_rows else None
                warehouse_status = "Доставлено" if linked_delivered else "На складе" if linked_stock else None

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
                        "request_warehouse_list": [
                            {
                                "request_warehouse_list_id": link.request_warehouse_list_id,
                                "warehouse_id": link.warehouse_id,
                                "warehouse_name": warehouses_by_id.get(link.warehouse_id).name if warehouses_by_id.get(link.warehouse_id) else None,
                                "warehouse_type": warehouses_by_id.get(link.warehouse_id).type if warehouses_by_id.get(link.warehouse_id) else None,
                                "request_qantity": link.request_qantity,
                                "warehouse_quantity": link.warehouse_quantity,
                            }
                            for link in linked_rows
                        ],
                        "warehouse_status": warehouse_status,
                        "request_warehouse_quantity": request_quantity,
                        "warehouse_quantity": warehouse_quantity,
                    }
                )

            total_positions = warehouse_positions_total
            answered_positions = len(mapped_request_item_ids_by_request_id.get(req.id, set()))

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
                    "answered_positions": answered_positions,
                    "total_positions": total_positions,
                    "warehouse_positions_total": warehouse_positions_total,
                    "warehouse_positions_linked": warehouse_positions_linked,
                    "warehouse_positions_on_stock": warehouse_positions_on_stock,
                    "warehouse_positions_delivered": warehouse_positions_delivered,
                    "status": None if not status else {"id": status.id, "name": status.name},
                    "items": request_items,
                    "logs": request_logs,
                    "documents": {
                        "invoices": invoices_by_request_id.get(req.id, []),
                    },
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

    def get_nomenclature_by_id(self, nomenclature_id: str) -> object | None:
        rows = self._get_nomenclature_by_ids([nomenclature_id])
        return rows[0] if rows else None

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

    def _get_nomenclature_by_ids(self, nomenclature_ids: list[str]) -> list[object]:
        unique_ids = list({item for item in nomenclature_ids if item})
        if not unique_ids:
            return []
        columns = self._get_table_columns("nomenclature")
        select_columns = [
            "id",
            "warehouse_category_id",
            "name",
            "unit_id",
        ]
        optional_columns = [
            "description",
            "article",
            "length",
            "width",
            "height",
            "weight",
            "vat_rate",
            "price_opt",
            "price_opt2",
            "price_retail",
            "created_at",
            "created_by",
        ]
        select_columns.extend([column for column in optional_columns if column in columns])
        rows = self.db.execute(
            text(
                f"SELECT {', '.join(select_columns)} "
                "FROM nomenclature "
                "WHERE id IN :ids"
            ).bindparams(bindparam("ids", expanding=True)),
            {"ids": unique_ids},
        ).mappings().all()
        return [self._build_nomenclature_namespace(row) for row in rows]

    def _get_table_columns(self, table_name: str) -> set[str]:
        if table_name in self._table_columns_cache:
            return self._table_columns_cache[table_name]
        try:
            rows = self.db.execute(text(f"SHOW COLUMNS FROM {table_name}")).mappings().all()
            columns = {str(row["Field"]) for row in rows}
        except Exception:
            columns = set()
        self._table_columns_cache[table_name] = columns
        return columns

    @staticmethod
    def _build_nomenclature_namespace(row) -> object:
        return SimpleNamespace(
            id=row.get("id"),
            warehouse_category_id=row.get("warehouse_category_id"),
            name=row.get("name"),
            description=row.get("description"),
            article=row.get("article"),
            unit_id=row.get("unit_id"),
            length=row.get("length"),
            width=row.get("width"),
            height=row.get("height"),
            weight=row.get("weight"),
            vat_rate=row.get("vat_rate"),
            price_opt=row.get("price_opt"),
            price_opt2=row.get("price_opt2"),
            price_retail=row.get("price_retail"),
            created_at=row.get("created_at"),
            created_by=row.get("created_by"),
        )

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

    def get_request_logs_by_user(
        self,
        user_id: str,
        status_name: str | None = None,
    ) -> list[RequestLog]:
        query = self.db.query(RequestLog).filter(RequestLog.user_id == user_id)
        if status_name:
            query = query.filter(RequestLog.status_name == status_name)
        return query.order_by(RequestLog.id.desc()).all()

    def count_request_logs_by_user_and_status(self, user_id: str, status_name: str) -> int:
        return (
            self.db.query(RequestLog)
            .filter(
                RequestLog.user_id == user_id,
                RequestLog.status_name == status_name,
            )
            .count()
        )

    # ─── Chat ID ────────────────────────────────────────────────────────────────

    def get_chat_ids_by_request(self, request_ids: list[int]) -> dict[int, int]:
        from app.models.chat import Chat
        if not request_ids:
            return {}
        chats = (
            self.db.query(Chat)
            .filter(Chat.type == "request", Chat.request_id.in_(request_ids))
            .all()
        )
        return {chat.request_id: chat.id for chat in chats if chat.request_id}

    def get_chat_id_by_request(self, request_id: int) -> int | None:
        from app.models.chat import Chat
        chat = (
            self.db.query(Chat)
            .filter(Chat.type == "request", Chat.request_id == request_id)
            .first()
        )
        return chat.id if chat else None
