import uuid

from sqlalchemy.orm import Session

from app.models.documents_link import DocumentsLink


class DocumentsLinkRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(
        self,
        document_linked_first: str | None = None,
        document_type_first: str | None = None,
        document_linked_second: str | None = None,
        document_type_second: str | None = None,
    ) -> list[DocumentsLink]:
        q = self.db.query(DocumentsLink)
        if document_linked_first:
            q = q.filter(DocumentsLink.document_linked_first == document_linked_first)
        if document_type_first:
            q = q.filter(DocumentsLink.document_type_first == document_type_first)
        if document_linked_second:
            q = q.filter(DocumentsLink.document_linked_second == document_linked_second)
        if document_type_second:
            q = q.filter(DocumentsLink.document_type_second == document_type_second)
        return q.order_by(DocumentsLink.created_at.desc()).all()

    def get_by_id(self, link_id: str) -> DocumentsLink | None:
        return self.db.query(DocumentsLink).filter(DocumentsLink.id == link_id).first()

    def get_by_document(self, document_id: str) -> list[DocumentsLink]:
        return self.db.query(DocumentsLink).filter(
            (DocumentsLink.document_linked_first == document_id) |
            (DocumentsLink.document_linked_second == document_id)
        ).order_by(DocumentsLink.created_at.desc()).all()

    def create(self, payload: dict) -> DocumentsLink:
        row = DocumentsLink(id=str(uuid.uuid4()), **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: DocumentsLink) -> DocumentsLink:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, row: DocumentsLink) -> None:
        self.db.delete(row)
        self.db.commit()
