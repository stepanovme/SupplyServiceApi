from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from sqlalchemy import func

from app.models.request_specification import RequestSpecification
from app.models.request_warehouse_list import RequestWarehouseList
from app.models.supply_request import RequestItem, StatusRef, SupplyRequest
from app.models.specification import Specification, SpecificationFile, SpecificationItem


class SpecificationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(self) -> list[Specification]:
        return self.db.query(Specification).order_by(Specification.created_at.desc(), Specification.id.desc()).all()

    def get_by_object_levels_id(self, object_levels_id: str, status_id: str | None = None) -> list[Specification]:
        query = self.db.query(Specification).filter(Specification.object_levels_id == object_levels_id)
        if status_id:
            query = query.filter(Specification.status_id == status_id)
        return query.order_by(Specification.created_at.desc(), Specification.id.desc()).all()

    def get_by_id(self, specification_id: str) -> Specification | None:
        return self.db.query(Specification).filter(Specification.id == specification_id).first()

    def create(self, payload: dict) -> Specification:
        row = Specification(id=str(uuid.uuid4()), **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: Specification) -> Specification:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, row: Specification) -> None:
        self.db.delete(row)
        self.db.commit()

    def get_status_names(self, status_ids: list[str]) -> dict[str, str]:
        unique_ids = list({status_id for status_id in status_ids if status_id})
        if not unique_ids:
            return {}
        rows = self.db.query(StatusRef.id, StatusRef.name).filter(StatusRef.id.in_(unique_ids)).all()
        return {row_id: row_name for row_id, row_name in rows}

    def get_files(self, specification_id: str) -> list[SpecificationFile]:
        return (
            self.db.query(SpecificationFile)
            .filter(SpecificationFile.specification_id == specification_id)
            .order_by(SpecificationFile.created_at.desc(), SpecificationFile.id.desc())
            .all()
        )

    def get_file_by_id(self, specification_id: str, file_id: str) -> SpecificationFile | None:
        return (
            self.db.query(SpecificationFile)
            .filter(
                SpecificationFile.specification_id == specification_id,
                SpecificationFile.id == file_id,
            )
            .first()
        )

    def create_file(self, specification_id: str, payload: dict) -> SpecificationFile:
        row = SpecificationFile(id=str(uuid.uuid4()), specification_id=specification_id, **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_file(self, row: SpecificationFile) -> SpecificationFile:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_file(self, row: SpecificationFile) -> None:
        self.db.delete(row)
        self.db.commit()

    def get_items(self, specification_id: str) -> list[SpecificationItem]:
        return (
            self.db.query(SpecificationItem)
            .filter(SpecificationItem.specification_id == specification_id)
            .order_by(SpecificationItem.num.asc(), SpecificationItem.created_at.asc(), SpecificationItem.id.asc())
            .all()
        )

    def get_item_by_id(self, specification_id: str, item_id: str) -> SpecificationItem | None:
        return (
            self.db.query(SpecificationItem)
            .filter(
                SpecificationItem.specification_id == specification_id,
                SpecificationItem.id == item_id,
            )
            .first()
        )

    def get_next_item_num(self, specification_id: str) -> int:
        row = (
            self.db.query(SpecificationItem.num)
            .filter(SpecificationItem.specification_id == specification_id)
            .order_by(SpecificationItem.num.desc())
            .first()
        )
        return (row[0] if row and row[0] is not None else 0) + 1

    def create_item(self, specification_id: str, payload: dict) -> SpecificationItem:
        row = SpecificationItem(id=str(uuid.uuid4()), specification_id=specification_id, **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_item(self, row: SpecificationItem) -> SpecificationItem:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_item(self, row: SpecificationItem) -> None:
        self.db.delete(row)
        self.db.commit()

    def get_summary(self, specification_id: str) -> list[dict]:
        REQUEST_APPROVED_STATUS_ID = "1ff33333-1312-11f1-aa8c-bc241127d0bd"

        rs_rows = (
            self.db.query(RequestSpecification)
            .filter(RequestSpecification.specification_id == specification_id)
            .all()
        )
        if not rs_rows:
            return []

        request_ids = list({row.request_id for row in rs_rows})
        valid_request_ids = {
            row.id
            for row in self.db.query(SupplyRequest.id)
            .filter(
                SupplyRequest.id.in_(request_ids),
                SupplyRequest.status_id == REQUEST_APPROVED_STATUS_ID,
            )
            .all()
        }

        valid_rs = [row for row in rs_rows if row.request_id in valid_request_ids]
        if not valid_rs:
            return []

        request_item_ids = [row.request_item_id for row in valid_rs]

        item_qty_map = {
            row.id: row.quantity
            for row in self.db.query(RequestItem.id, RequestItem.quantity)
            .filter(RequestItem.id.in_(request_item_ids))
            .all()
        }

        wh_qty_map: dict[str, float] = {}
        wh_rows = (
            self.db.query(
                RequestWarehouseList.request_item_id,
                func.coalesce(func.sum(RequestWarehouseList.request_qantity), 0),
            )
            .filter(RequestWarehouseList.request_item_id.in_(request_item_ids))
            .group_by(RequestWarehouseList.request_item_id)
            .all()
        )
        for request_item_id, total in wh_rows:
            wh_qty_map[request_item_id] = float(total)

        spec_item_ids = list({row.specification_item_id for row in valid_rs})
        item_names = {
            row.id: row.name
            for row in self.db.query(SpecificationItem.id, SpecificationItem.name)
            .filter(SpecificationItem.id.in_(spec_item_ids))
            .all()
        }

        agg: dict[str, dict] = {}
        for row in valid_rs:
            spec_item_id = row.specification_item_id
            if spec_item_id not in agg:
                agg[spec_item_id] = {
                    "specification_item_id": spec_item_id,
                    "specification_item_name": item_names.get(spec_item_id),
                    "ordered_quantity": 0,
                    "warehouse_quantity": 0,
                }
            agg[spec_item_id]["ordered_quantity"] += item_qty_map.get(row.request_item_id, 0)
            agg[spec_item_id]["warehouse_quantity"] += wh_qty_map.get(row.request_item_id, 0)

        return list(agg.values())

    # ─── Chat ID ────────────────────────────────────────────────────────────

    def get_chat_ids_by_specification(self, specification_ids: list[str]) -> dict[str, int]:
        from app.models.chat import Chat
        if not specification_ids:
            return {}
        chats = (
            self.db.query(Chat)
            .filter(Chat.type == "specification", Chat.specification_id.in_(specification_ids))
            .all()
        )
        return {chat.specification_id: chat.id for chat in chats if chat.specification_id}

    def get_chat_id_by_specification(self, specification_id: str) -> int | None:
        from app.models.chat import Chat
        chat = (
            self.db.query(Chat)
            .filter(Chat.type == "specification", Chat.specification_id == specification_id)
            .first()
        )
        return chat.id if chat else None
