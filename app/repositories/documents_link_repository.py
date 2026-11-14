import uuid

from sqlalchemy import and_, or_
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

    def get_by_document(self, document_id: str, document_type: str | None = None) -> list[DocumentsLink]:
        """Links of a document. Ids of different types can coincide (act 5 and contract 5), so pass the type."""
        first = DocumentsLink.document_linked_first == document_id
        second = DocumentsLink.document_linked_second == document_id
        if document_type:
            first = and_(first, DocumentsLink.document_type_first == document_type)
            second = and_(second, DocumentsLink.document_type_second == document_type)
        return self.db.query(DocumentsLink).filter(or_(first, second)).order_by(DocumentsLink.created_at.desc()).all()

    def counts_for_documents(self, document_type: str, ids: list[str], other_types: list[str]) -> dict[str, dict[str, int]]:
        """{document_id: {other_type: count}} for many documents of one type in a single query."""
        ids = [str(i) for i in ids]
        if not ids:
            return {}
        rows = self.db.query(DocumentsLink).filter(or_(
            and_(DocumentsLink.document_type_first == document_type, DocumentsLink.document_linked_first.in_(ids),
                 DocumentsLink.document_type_second.in_(other_types)),
            and_(DocumentsLink.document_type_second == document_type, DocumentsLink.document_linked_second.in_(ids),
                 DocumentsLink.document_type_first.in_(other_types)),
        )).all()
        result: dict[str, dict[str, int]] = {}
        for r in rows:
            if r.document_type_first == document_type and r.document_linked_first in ids and r.document_type_second in other_types:
                mine, other = r.document_linked_first, r.document_type_second
            else:
                mine, other = r.document_linked_second, r.document_type_first
            bucket = result.setdefault(mine, {})
            bucket[other] = bucket.get(other, 0) + 1
        return result

    def find_pair(self, id_a: str, type_a: str, id_b: str, type_b: str) -> DocumentsLink | None:
        """An existing link between two documents, saved in either order."""
        return self.db.query(DocumentsLink).filter(or_(
            and_(DocumentsLink.document_linked_first == id_a, DocumentsLink.document_type_first == type_a,
                 DocumentsLink.document_linked_second == id_b, DocumentsLink.document_type_second == type_b),
            and_(DocumentsLink.document_linked_first == id_b, DocumentsLink.document_type_first == type_b,
                 DocumentsLink.document_linked_second == id_a, DocumentsLink.document_type_second == type_a),
        )).order_by(DocumentsLink.created_at).first()

    def delete_for_document(self, document_type: str, document_id: str) -> int:
        """Removes every link of a document (called when the document itself is deleted). Does not commit."""
        rows = self.get_by_document(str(document_id), document_type)
        for row in rows:
            self.db.delete(row)
        return len(rows)

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
