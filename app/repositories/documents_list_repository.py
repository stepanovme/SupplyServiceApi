from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import msk_now
from app.models.documents_list import DocumentsList


class DocumentsListRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(self, unattached_only: bool = False) -> list[DocumentsList]:
        q = self.db.query(DocumentsList)
        if unattached_only:
            q = q.filter(DocumentsList.document_id.is_(None), DocumentsList.document_type.is_(None))
        return q.order_by(DocumentsList.uploaded_at.desc(), DocumentsList.id.desc()).all()

    def get_by_user_id(self, user_id: str, unattached_only: bool = False) -> list[DocumentsList]:
        q = self.db.query(DocumentsList).filter(DocumentsList.uploaded_by == user_id)
        if unattached_only:
            q = q.filter(DocumentsList.document_id.is_(None), DocumentsList.document_type.is_(None))
        return q.order_by(DocumentsList.uploaded_at.desc(), DocumentsList.id.desc()).all()

    def get_document_ids_by_user(self, user_id: str) -> list[int]:
        rows = self.db.query(DocumentsList.id).filter(DocumentsList.uploaded_by == user_id).all()
        return [row[0] for row in rows]

    def get_all_document_ids(self) -> list[int]:
        rows = self.db.query(DocumentsList.id).all()
        return [row[0] for row in rows]

    def get_document_ids_by_counterparty(self, counterparty_ids: list[str]) -> list[int]:
        if not counterparty_ids:
            return []
        rows = self.db.query(DocumentsList.id).filter(
            or_(
                DocumentsList.from_whom_id.in_(counterparty_ids),
                DocumentsList.customer_id.in_(counterparty_ids),
                DocumentsList.contractor_id.in_(counterparty_ids),
            )
        ).all()
        return [row[0] for row in rows]

    def get_by_id(self, document_id: int) -> DocumentsList | None:
        return self.db.query(DocumentsList).filter(DocumentsList.id == document_id).first()

    def get_by_linked_file_id(self, linked_file_id: str) -> DocumentsList | None:
        return self.db.query(DocumentsList).filter(DocumentsList.linked_file_id == linked_file_id).first()

    def create(self, payload: dict) -> DocumentsList:
        row = DocumentsList(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: DocumentsList) -> DocumentsList:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, row: DocumentsList) -> None:
        self.db.delete(row)
        self.db.commit()

    def touch(self, row: DocumentsList, user_id: str) -> DocumentsList:
        row.updated_at = msk_now()
        row.updated_by = user_id
        self.db.commit()
        self.db.refresh(row)
        return row

    def unlink_by_linked_file_id(self, linked_file_id: str) -> None:
        row = self.get_by_linked_file_id(linked_file_id)
        if not row:
            return
        row.document_id = None
        row.document_type = None
        row.linked_file_id = None
        row.updated_at = msk_now()
        self.db.commit()

    def rename_by_linked_file_id(self, linked_file_id: str, new_name: str) -> None:
        row = self.get_by_linked_file_id(linked_file_id)
        if not row:
            return
        row.original_name = new_name
        row.updated_at = msk_now()
        self.db.commit()