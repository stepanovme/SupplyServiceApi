import uuid

from sqlalchemy.orm import Session

from app.models.supply_request import StatusRef
from app.models.upd_document import UpdDocument, UpdDocumentItem
from app.models.warehouse import Warehouse


class UpdDocumentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def rollback(self) -> None:
        self.db.rollback()

    def create_document(self, payload: dict) -> UpdDocument:
        row = UpdDocument(**payload)
        self.db.add(row)
        try:
            self.db.commit()
            self.db.refresh(row)
        except Exception:
            self.db.rollback()
            raise
        return row

    def get_documents(self, warehouse_id: str | None = None) -> list[UpdDocument]:
        query = self.db.query(UpdDocument)
        if warehouse_id:
            query = query.filter(UpdDocument.warehouse_id == warehouse_id)
        return query.order_by(UpdDocument.created_at.desc()).all()

    def get_document_by_id(self, document_id: str) -> UpdDocument | None:
        return self.db.query(UpdDocument).filter(UpdDocument.id == document_id).first()

    def save_document(self, row: UpdDocument) -> UpdDocument:
        try:
            self.db.commit()
            self.db.refresh(row)
        except Exception:
            self.db.rollback()
            raise
        return row

    def create_document_item(self, document_id: str, payload: dict) -> UpdDocumentItem:
        row = UpdDocumentItem(id=str(uuid.uuid4()), upd_documents_id=document_id, **payload)
        self.db.add(row)
        try:
            self.db.commit()
            self.db.refresh(row)
        except Exception:
            self.db.rollback()
            raise
        return row

    def get_document_items(self, document_id: str) -> list[UpdDocumentItem]:
        return (
            self.db.query(UpdDocumentItem)
            .filter(UpdDocumentItem.upd_documents_id == document_id)
            .order_by(UpdDocumentItem.id.asc())
            .all()
        )

    def get_document_item_by_id(self, document_id: str, item_id: str) -> UpdDocumentItem | None:
        return (
            self.db.query(UpdDocumentItem)
            .filter(
                UpdDocumentItem.upd_documents_id == document_id,
                UpdDocumentItem.id == item_id,
            )
            .first()
        )

    def save_document_item(self, row: UpdDocumentItem) -> UpdDocumentItem:
        try:
            self.db.commit()
            self.db.refresh(row)
        except Exception:
            self.db.rollback()
            raise
        return row

    def delete_document_item(self, row: UpdDocumentItem) -> None:
        self.db.delete(row)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def delete_document_items_by_document_id(self, document_id: str) -> None:
        (
            self.db.query(UpdDocumentItem)
            .filter(UpdDocumentItem.upd_documents_id == document_id)
            .delete(synchronize_session=False)
        )
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def get_status_name(self, status_id: str | None) -> str | None:
        if not status_id:
            return None
        row = self.db.query(StatusRef).filter(StatusRef.id == status_id).first()
        return row.name if row else None

    def get_warehouse_names(self, warehouse_ids: list[str]) -> dict[str, str]:
        unique_ids = list({warehouse_id for warehouse_id in warehouse_ids if warehouse_id})
        if not unique_ids:
            return {}
        rows = (
            self.db.query(Warehouse.id, Warehouse.name)
            .filter(Warehouse.id.in_(unique_ids))
            .all()
        )
        return {str(warehouse_id): warehouse_name for warehouse_id, warehouse_name in rows}
