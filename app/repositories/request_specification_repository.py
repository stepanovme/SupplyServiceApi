from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from sqlalchemy import String

from app.models.request_specification import RequestSpecification
from app.models.specification import SpecificationItem


class RequestSpecificationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(self) -> list[RequestSpecification]:
        return (
            self.db.query(RequestSpecification)
            .order_by(RequestSpecification.created_at.desc(), RequestSpecification.request_specification_id.desc())
            .all()
        )

    def get_by_id(self, row_id: str) -> RequestSpecification | None:
        return self.db.query(RequestSpecification).filter(RequestSpecification.request_specification_id == row_id).first()

    def get_by_request_id(self, request_id: int) -> list[RequestSpecification]:
        return (
            self.db.query(RequestSpecification)
            .filter(RequestSpecification.request_id == request_id)
            .order_by(RequestSpecification.created_at.desc(), RequestSpecification.request_specification_id.desc())
            .all()
        )

    def get_by_specification_id(self, specification_id: str) -> list[RequestSpecification]:
        return (
            self.db.query(RequestSpecification)
            .filter(RequestSpecification.specification_id == specification_id)
            .order_by(RequestSpecification.created_at.desc(), RequestSpecification.request_specification_id.desc())
            .all()
        )

    def get_by_request_item_id(self, request_item_id: str) -> list[RequestSpecification]:
        return (
            self.db.query(RequestSpecification)
            .filter(RequestSpecification.request_item_id == request_item_id)
            .order_by(RequestSpecification.created_at.desc(), RequestSpecification.request_specification_id.desc())
            .all()
        )

    def get_by_specification_item_id(self, specification_item_id: str) -> list[RequestSpecification]:
        return (
            self.db.query(RequestSpecification)
            .filter(RequestSpecification.specification_item_id == specification_item_id)
            .order_by(RequestSpecification.created_at.desc(), RequestSpecification.request_specification_id.desc())
            .all()
        )

    def create(self, payload: dict) -> RequestSpecification:
        row = RequestSpecification(request_specification_id=str(uuid.uuid4()), **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: RequestSpecification) -> RequestSpecification:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, row: RequestSpecification) -> None:
        self.db.delete(row)
        self.db.commit()

    def get_specification_item_names(self, specification_item_ids: list[str]) -> dict[str, str]:
        rows = (
            self.db.query(SpecificationItem.id, SpecificationItem.name)
            .filter(SpecificationItem.id.in_(specification_item_ids))
            .all()
        )
        return {row.id: row.name for row in rows if row.name}
