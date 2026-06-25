from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.request_warehouse_list import RequestWarehouseList


class RequestWarehouseListRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(self) -> list[RequestWarehouseList]:
        return self.db.query(RequestWarehouseList).order_by(RequestWarehouseList.created_at.desc(), RequestWarehouseList.request_warehouse_list_id.desc()).all()

    def get_by_id(self, row_id: str) -> RequestWarehouseList | None:
        return self.db.query(RequestWarehouseList).filter(RequestWarehouseList.request_warehouse_list_id == row_id).first()

    def get_by_request_id(self, request_id: int) -> list[RequestWarehouseList]:
        return (
            self.db.query(RequestWarehouseList)
            .filter(RequestWarehouseList.request_id == request_id)
            .order_by(RequestWarehouseList.created_at.desc(), RequestWarehouseList.request_warehouse_list_id.desc())
            .all()
        )

    def create(self, payload: dict) -> RequestWarehouseList:
        row = RequestWarehouseList(request_warehouse_list_id=str(uuid.uuid4()), **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: RequestWarehouseList) -> RequestWarehouseList:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, row: RequestWarehouseList) -> None:
        self.db.delete(row)
        self.db.commit()
