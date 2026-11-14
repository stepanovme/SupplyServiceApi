import uuid
from collections import defaultdict
from types import SimpleNamespace

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceItem, InvoicePayment
from app.models.item_mapping import ItemMapping
from app.models.delivery import Delivery, DeliveryItem
from app.models.delivery_item_mapping import DeliveryItemMapping
from app.models.supply_request import (
    NomenclatureRef,
    RequestEventLog,
    RequestItem,
    RequestItemSnapshot,
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

        snapshots = self.db.query(RequestItemSnapshot).filter(RequestItemSnapshot.request_id.in_(request_ids)).all()
        snapshots_by_item_id = defaultdict(list)
        for snap in snapshots:
            snapshots_by_item_id[snap.request_item_id].append(snap)

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

        invoice_item_ids = list({m.invoice_item_id for m in mappings if m.invoice_item_id})
        invoice_items_by_id = {}
        if invoice_item_ids:
            invoice_items_rows = self.db.query(InvoiceItem).filter(InvoiceItem.id.in_(invoice_item_ids)).all()
            invoice_items_by_id = {row.id: row for row in invoice_items_rows}

        invoices = self.db.query(Invoice).filter(Invoice.request_id.in_(request_ids)).all()
        invoices_by_request_id = defaultdict(list)
        invoices_by_id = {inv.id: inv for inv in invoices}
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

        invoice_ids_for_payments = list({m.invoice_id for m in mappings if m.invoice_id})
        payments_by_invoice: dict[int, float] = defaultdict(float)
        if invoice_ids_for_payments:
            payments = self.db.query(InvoicePayment).filter(InvoicePayment.invoice_id.in_(invoice_ids_for_payments)).all()
            for p in payments:
                payments_by_invoice[p.invoice_id] += p.paid or 0

        mappings_by_request_item: dict[str, list] = defaultdict(list)
        for m in mappings:
            inv_item = invoice_items_by_id.get(m.invoice_item_id) if m.invoice_item_id else None
            inv = invoices_by_id.get(m.invoice_id) if m.invoice_id else None
            inv_status = statuses_by_id.get(inv.status) if inv else None
            inv_paid = payments_by_invoice.get(m.invoice_id, 0) if m.invoice_id else 0
            inv_total = inv.total_amount if inv else 0
            inv_payment_percent = round((inv_paid / inv_total * 100) if inv_total and inv_total > 0 else 0, 1)
            mappings_by_request_item[m.request_item_id].append({
                "invoice_item_id": m.invoice_item_id,
                "invoice_id": m.invoice_id,
                "invoice_num": inv.num if inv else None,
                "invoice_date": inv.date if inv else None,
                "invoice_status": inv_status.name if inv_status else None,
                "invoice_total_amount": inv_total,
                "invoice_paid_amount": round(inv_paid, 2),
                "invoice_payment_percent": inv_payment_percent,
                "group_number": m.group_number,
                "match_type": m.match_type,
                "mapped_quantity": m.mapped_quantity,
                "invoice_item_name": inv_item.name if inv_item else None,
                "invoice_item_quantity": inv_item.quantity if inv_item else None,
                "invoice_item_price": inv_item.price if inv_item else None,
            })

        paid_quantity_by_request_item: dict[str, float] = defaultdict(float)
        for m in mappings:
            if m.invoice_id and m.invoice_item_id:
                inv = invoices_by_id.get(m.invoice_id)
                if inv and inv.total_amount and inv.total_amount > 0:
                    paid_ratio = payments_by_invoice.get(m.invoice_id, 0) / inv.total_amount
                    paid_quantity_by_request_item[m.request_item_id] += (m.mapped_quantity or 0) * paid_ratio

        deliveries = self.db.query(Delivery).filter(Delivery.request_id.in_(request_ids)).all()
        delivery_ids = [d.id for d in deliveries]
        delivery_items = self.db.query(DeliveryItem).filter(DeliveryItem.delivery_id.in_(delivery_ids)).all() if delivery_ids else []
        delivery_item_ids = [di.id for di in delivery_items]
        delivery_mappings = self.db.query(DeliveryItemMapping).filter(DeliveryItemMapping.delivery_item_id.in_(delivery_item_ids)).all() if delivery_item_ids else []

        delivered_by_request_item: dict[str, dict] = defaultdict(lambda: {"delivered_quantity": 0.0, "delivery_count": 0})
        deliveries_by_item: dict[str, list] = defaultdict(list)
        for dm in delivery_mappings:
            for di in delivery_items:
                if di.id == dm.delivery_item_id and di.request_item_id:
                    delivered_by_request_item[di.request_item_id]["delivered_quantity"] += dm.delivery_quantity or 0
                    delivered_by_request_item[di.request_item_id]["delivery_count"] += 1
                    deliveries_by_item[di.request_item_id].append({
                        "delivery_at": dm.delivery_at,
                        "delivery_quantity": dm.delivery_quantity,
                    })

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

                item_snaps = snapshots_by_item_id.get(item.id, [])
                request_items.append(
                    {
                        "id": item.id,
                        "request_id": item.request_id,
                        "num": item.num,
                        "name": item.name,
                        "quantity": float(item.quantity),
                        "comment": item.comment,
                        "is_new": getattr(item, "is_new", False),
                        "original_quantity": float(item_snaps[0].original_quantity) if item_snaps else float(item.quantity),
                        "quantity_diff": float(item.quantity) - float(item_snaps[0].original_quantity if item_snaps else item.quantity),
                        "snapshots": [
                            {
                                "id": s.id,
                                "original_quantity": s.original_quantity,
                                "snapshot_quantity": s.snapshot_quantity,
                                "quantity_diff": s.quantity_diff,
                                "created_by": s.created_by,
                                "created_at": s.created_at,
                            }
                            for s in item_snaps
                        ],
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
                        "delivered_quantity": delivered_by_request_item.get(item.id, {}).get("delivered_quantity", 0),
                        "is_fully_delivered": (delivered_by_request_item.get(item.id, {}).get("delivered_quantity", 0) >= float(item.quantity)) if item.quantity else False,
                        "deliveries": sorted(deliveries_by_item.get(item.id, []), key=lambda x: x["delivery_at"] or ""),
                        "invoice_mappings": mappings_by_request_item.get(item.id, []),
                        "paid_quantity": round(paid_quantity_by_request_item.get(item.id, 0), 2),
                        "is_fully_paid": (paid_quantity_by_request_item.get(item.id, 0) >= float(item.quantity)) if item.quantity else False,
                        "payment_percent": round((paid_quantity_by_request_item.get(item.id, 0) / float(item.quantity) * 100) if item.quantity else 0, 1),
                        "is_answered": item.id in mapped_request_item_ids_by_request_id.get(req.id, set()),
                    }
                )

            total_positions = warehouse_positions_total
            answered_positions = len(mapped_request_item_ids_by_request_id.get(req.id, set()))

            total_quantity = sum(float(i.quantity or 0) for i in items_by_request_id.get(req.id, []))
            total_paid = sum(paid_quantity_by_request_item.get(i.id, 0) for i in items_by_request_id.get(req.id, []))
            payment_percent_overall = round((total_paid / total_quantity * 100) if total_quantity > 0 else 0, 1)

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
                    "object_type": req.object_type,
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
                    "copied_from_request_id": req.copied_from_request_id,
                    "split_from_request_id": req.split_from_request_id,
                    "split_to_request_ids": [int(x) for x in (req.split_to_request_ids or "").split(",") if x.strip()] if req.split_to_request_ids else None,
                    "items_count_before_split": req.items_count_before_split,
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
                        "total_quantity": round(total_quantity, 2),
                        "paid_quantity": round(total_paid, 2),
                        "payment_percent": payment_percent_overall,
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

    def delete(self, request_row: SupplyRequest) -> None:
        self.db.delete(request_row)
        self.db.commit()

    def copy_request(self, source_id: int, new_request: SupplyRequest, items: list[RequestItem]) -> SupplyRequest:
        self.db.add(new_request)
        self.db.flush()

        for item in items:
            new_item = RequestItem(
                id=str(uuid.uuid4()),
                request_id=new_request.id,
                num=item.num,
                nomenclature_id=item.nomenclature_id,
                name=item.name,
                unit_id=item.unit_id,
                quantity=item.quantity,
                warehouse_category_id=item.warehouse_category_id,
                comment=item.comment,
            )
            self.db.add(new_item)

        self.db.commit()
        self.db.refresh(new_request)
        return new_request

    def split_request(
        self,
        source: SupplyRequest,
        new_requests_with_items: list[tuple[SupplyRequest, list[RequestItem], dict[str, float | None]]],
    ) -> list[SupplyRequest]:
        items_count_before = (
            self.db.query(RequestItem).filter(RequestItem.request_id == source.id).count()
        )
        source.items_count_before_split = items_count_before

        created_ids = []
        for new_request, items_to_move, quantities in new_requests_with_items:
            self.db.add(new_request)
            self.db.flush()

            for item in items_to_move:
                new_qty = quantities.get(item.id)
                if new_qty is None:
                    new_qty = item.quantity
                new_item = RequestItem(
                    id=str(uuid.uuid4()),
                    request_id=new_request.id,
                    num=item.num,
                    nomenclature_id=item.nomenclature_id,
                    name=item.name,
                    unit_id=item.unit_id,
                    quantity=new_qty,
                    warehouse_category_id=item.warehouse_category_id,
                    comment=item.comment,
                )
                self.db.add(new_item)
                self.db.delete(item)

            created_ids.append(new_request.id)

        source.split_to_request_ids = ",".join(str(x) for x in created_ids)

        self.db.commit()
        self.db.refresh(source)
        return source

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

    def get_request_logs_by_request(self, request_id: int) -> list[RequestLog]:
        return (
            self.db.query(RequestLog)
            .filter(RequestLog.request_id == str(request_id))
            .all()
        )

    def get_request_log_user_ids(self, request_id: int) -> list[str]:
        rows = (
            self.db.query(RequestLog.user_id)
            .filter(RequestLog.request_id == str(request_id))
            .distinct()
            .all()
        )
        return [row[0] for row in rows if row[0]]

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

    # ─── RequestItemSnapshot ──────────────────────────────────────────────────

    def has_request_items(self, request_id: int) -> bool:
        return (
            self.db.query(RequestItem.id).filter(RequestItem.request_id == request_id).first()
            is not None
        )

    def get_snapshots_by_request(self, request_id: int) -> list[RequestItemSnapshot]:
        return (
            self.db.query(RequestItemSnapshot)
            .filter(RequestItemSnapshot.request_id == request_id)
            .all()
        )

    def get_request_items_by_request(self, request_id: int) -> list[RequestItem]:
        return (
            self.db.query(RequestItem)
            .filter(RequestItem.request_id == request_id)
            .order_by(RequestItem.num)
            .all()
        )

    def get_snapshot_by_item(self, request_item_id: str) -> RequestItemSnapshot | None:
        return (
            self.db.query(RequestItemSnapshot)
            .filter(RequestItemSnapshot.request_item_id == request_item_id)
            .first()
        )

    def create_snapshot(
        self, request_id: int, request_item_id: str,
        original_quantity: float, snapshot_quantity: float, quantity_diff: float,
        created_by: str,
    ) -> RequestItemSnapshot:
        item = RequestItemSnapshot(
            id=str(uuid.uuid4()),
            request_id=request_id,
            request_item_id=request_item_id,
            original_quantity=original_quantity,
            snapshot_quantity=snapshot_quantity,
            quantity_diff=quantity_diff,
            created_by=created_by,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    # ─── RequestEventLog ──────────────────────────────────────────────────────

    def create_event_log(
        self, request_id: int, user_id: str,
        event_type: str, description: str | None = None,
        metadata_json: str | None = None,
    ) -> RequestEventLog:
        item = RequestEventLog(
            id=str(uuid.uuid4()),
            request_id=request_id,
            user_id=user_id,
            event_type=event_type,
            description=description,
            metadata_json=metadata_json,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_event_logs_by_request(self, request_id: int) -> list[RequestEventLog]:
        return (
            self.db.query(RequestEventLog)
            .filter(RequestEventLog.request_id == request_id)
            .order_by(RequestEventLog.created_at.desc())
            .all()
        )

    def check_delivery_and_update_status(self, request_id: int, delivered_status_id: str = "9965dcae-ab52-11f1-97bf-bc241127d0bd") -> bool:
        from app.models.delivery import Delivery, DeliveryItem
        from app.models.delivery_item_mapping import DeliveryItemMapping

        request = self.db.query(SupplyRequest).filter(SupplyRequest.id == request_id).first()
        if not request:
            return False

        items = self.db.query(RequestItem).filter(RequestItem.request_id == request_id).all()
        if not items:
            return False

        deliveries = self.db.query(Delivery).filter(Delivery.request_id == request_id).all()
        if not deliveries:
            return False

        delivery_ids = [d.id for d in deliveries]
        delivery_items = self.db.query(DeliveryItem).filter(DeliveryItem.delivery_id.in_(delivery_ids)).all()
        if not delivery_items:
            return False

        delivery_item_ids = [di.id for di in delivery_items]
        delivery_mappings = self.db.query(DeliveryItemMapping).filter(DeliveryItemMapping.delivery_item_id.in_(delivery_item_ids)).all()

        delivered_by_item: dict[str, float] = {}
        for dm in delivery_mappings:
            for di in delivery_items:
                if di.id == dm.delivery_item_id and di.request_item_id:
                    delivered_by_item[di.request_item_id] = delivered_by_item.get(di.request_item_id, 0) + (dm.delivery_quantity or 0)

        all_fully_delivered = True
        for item in items:
            delivered = delivered_by_item.get(item.id, 0)
            if not item.quantity or delivered < float(item.quantity):
                all_fully_delivered = False
                break

        if all_fully_delivered and request.status_id != delivered_status_id:
            request.status_id = delivered_status_id
            self.db.commit()
            return True

        return False
