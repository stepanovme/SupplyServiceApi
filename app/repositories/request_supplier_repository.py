from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.supply_request import StatusRef, SupplyRequest
from app.models.request_supplier import (
    RequestSupplier,
    RequestSupplierLink,
    RequestSupplierEmailSender,
    RequestSupplierFile,
    RequestSupplierItem,
    RequestSupplierRecipient,
)


class RequestSupplierRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(self) -> list[RequestSupplier]:
        return self.db.query(RequestSupplier).order_by(RequestSupplier.created_at.desc()).all()

    def get_by_id(self, request_supplier_id: str) -> RequestSupplier | None:
        return self.db.query(RequestSupplier).filter(RequestSupplier.id == request_supplier_id).first()

    def create(self, payload: dict) -> RequestSupplier:
        row = RequestSupplier(id=str(uuid.uuid4()), **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: RequestSupplier) -> RequestSupplier:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, row: RequestSupplier) -> None:
        self.db.delete(row)
        self.db.commit()

    def get_status_names(self, status_ids: list[str]) -> dict[str, str]:
        unique_ids = list({status_id for status_id in status_ids if status_id})
        if not unique_ids:
            return {}
        rows = self.db.query(StatusRef.id, StatusRef.name).filter(StatusRef.id.in_(unique_ids)).all()
        return {row_id: row_name for row_id, row_name in rows}

    def get_requests_by_ids(self, request_ids: list[int]) -> dict[int, SupplyRequest]:
        unique_ids = list({request_id for request_id in request_ids if request_id is not None})
        if not unique_ids:
            return {}
        rows = self.db.query(SupplyRequest).filter(SupplyRequest.id.in_(unique_ids)).all()
        return {row.id: row for row in rows}

    def get_items(self, request_supplier_id: str) -> list[RequestSupplierItem]:
        return (
            self.db.query(RequestSupplierItem)
            .filter(RequestSupplierItem.request_supplier_id == request_supplier_id)
            .order_by(RequestSupplierItem.id.asc())
            .all()
        )

    def get_item_by_id(self, request_supplier_id: str, item_id: str) -> RequestSupplierItem | None:
        return (
            self.db.query(RequestSupplierItem)
            .filter(
                RequestSupplierItem.request_supplier_id == request_supplier_id,
                RequestSupplierItem.id == item_id,
            )
            .first()
        )

    def create_item(self, request_supplier_id: str, payload: dict) -> RequestSupplierItem:
        row = RequestSupplierItem(id=str(uuid.uuid4()), request_supplier_id=request_supplier_id, **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_item(self, row: RequestSupplierItem) -> RequestSupplierItem:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_item(self, row: RequestSupplierItem) -> None:
        self.db.delete(row)
        self.db.commit()

    def get_email_senders(self, request_supplier_id: str) -> list[RequestSupplierEmailSender]:
        return (
            self.db.query(RequestSupplierEmailSender)
            .filter(RequestSupplierEmailSender.request_supplier_id == request_supplier_id)
            .order_by(RequestSupplierEmailSender.id.asc())
            .all()
        )

    def get_email_sender_by_id(self, request_supplier_id: str, row_id: str) -> RequestSupplierEmailSender | None:
        return (
            self.db.query(RequestSupplierEmailSender)
            .filter(
                RequestSupplierEmailSender.request_supplier_id == request_supplier_id,
                RequestSupplierEmailSender.id == row_id,
            )
            .first()
        )

    def create_email_sender(self, request_supplier_id: str, payload: dict) -> RequestSupplierEmailSender:
        row = RequestSupplierEmailSender(id=str(uuid.uuid4()), request_supplier_id=request_supplier_id, **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_email_sender(self, row: RequestSupplierEmailSender) -> RequestSupplierEmailSender:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_email_sender(self, row: RequestSupplierEmailSender) -> None:
        self.db.delete(row)
        self.db.commit()

    def get_files(self, request_supplier_id: str) -> list[RequestSupplierFile]:
        return (
            self.db.query(RequestSupplierFile)
            .filter(RequestSupplierFile.request_supplier_id == request_supplier_id)
            .order_by(RequestSupplierFile.uploaded_at.desc(), RequestSupplierFile.id.desc())
            .all()
        )

    def get_file_by_id(self, request_supplier_id: str, row_id: str) -> RequestSupplierFile | None:
        return (
            self.db.query(RequestSupplierFile)
            .filter(
                RequestSupplierFile.request_supplier_id == request_supplier_id,
                RequestSupplierFile.id == row_id,
            )
            .first()
        )

    def create_file(self, request_supplier_id: str, payload: dict) -> RequestSupplierFile:
        row = RequestSupplierFile(id=str(uuid.uuid4()), request_supplier_id=request_supplier_id, **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_file(self, row: RequestSupplierFile) -> RequestSupplierFile:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_file(self, row: RequestSupplierFile) -> None:
        self.db.delete(row)
        self.db.commit()

    def get_recipients(self, request_supplier_id: str) -> list[RequestSupplierRecipient]:
        return (
            self.db.query(RequestSupplierRecipient)
            .filter(RequestSupplierRecipient.request_supplier_id == request_supplier_id)
            .order_by(RequestSupplierRecipient.id.asc())
            .all()
        )

    def get_recipient_by_id(self, request_supplier_id: str, row_id: str) -> RequestSupplierRecipient | None:
        return (
            self.db.query(RequestSupplierRecipient)
            .filter(
                RequestSupplierRecipient.request_supplier_id == request_supplier_id,
                RequestSupplierRecipient.id == row_id,
            )
            .first()
        )

    def create_recipient(self, request_supplier_id: str, payload: dict) -> RequestSupplierRecipient:
        row = RequestSupplierRecipient(id=str(uuid.uuid4()), request_supplier_id=request_supplier_id, **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_recipient(self, row: RequestSupplierRecipient) -> RequestSupplierRecipient:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_recipient(self, row: RequestSupplierRecipient) -> None:
        self.db.delete(row)
        self.db.commit()

    def get_links(self, request_supplier_id: str) -> list[RequestSupplierLink]:
        return (
            self.db.query(RequestSupplierLink)
            .filter(RequestSupplierLink.request_supplier_id == request_supplier_id)
            .order_by(RequestSupplierLink.created_at.desc(), RequestSupplierLink.id.desc())
            .all()
        )

    def get_link_by_id(self, request_supplier_id: str, row_id: str) -> RequestSupplierLink | None:
        return (
            self.db.query(RequestSupplierLink)
            .filter(
                RequestSupplierLink.request_supplier_id == request_supplier_id,
                RequestSupplierLink.id == row_id,
            )
            .first()
        )

    def get_link_by_code(self, code: str, active_only: bool = True) -> RequestSupplierLink | None:
        query = self.db.query(RequestSupplierLink).filter(RequestSupplierLink.code == code)
        if active_only:
            query = query.filter(RequestSupplierLink.status == "active")
        return query.order_by(RequestSupplierLink.created_at.desc(), RequestSupplierLink.id.desc()).first()

    def get_link_by_recipient_id(
        self,
        request_supplier_id: str,
        request_supplier_recipient_id: str,
        active_only: bool = True,
    ) -> RequestSupplierLink | None:
        query = self.db.query(RequestSupplierLink).filter(
            RequestSupplierLink.request_supplier_id == request_supplier_id,
            RequestSupplierLink.request_supplier_recipient_id == request_supplier_recipient_id,
        )
        if active_only:
            query = query.filter(RequestSupplierLink.status == "active")
        return query.order_by(RequestSupplierLink.created_at.desc(), RequestSupplierLink.id.desc()).first()

    def create_link(self, request_supplier_id: str, payload: dict) -> RequestSupplierLink:
        row = RequestSupplierLink(id=str(uuid.uuid4()), request_supplier_id=request_supplier_id, **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_link(self, row: RequestSupplierLink) -> RequestSupplierLink:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_link(self, row: RequestSupplierLink) -> None:
        self.db.delete(row)
        self.db.commit()
