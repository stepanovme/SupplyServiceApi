from fastapi import HTTPException, status

from app.models.contract import Contract
from app.models.documents_link import (
    DocumentsLink,
    DocumentsLinkCreate,
    DocumentsLinkUpdate,
)
from app.models.letter import Letter, LetterFile
from app.repositories.contract_repository import ContractFile
from app.repositories.documents_link_repository import DocumentsLinkRepository


class DocumentsLinkService:
    def __init__(self, repo: DocumentsLinkRepository) -> None:
        self.repo = repo

    def get_all(
        self,
        document_linked_first: str | None = None,
        document_type_first: str | None = None,
        document_linked_second: str | None = None,
        document_type_second: str | None = None,
    ) -> list[dict]:
        rows = self.repo.get_all(
            document_linked_first, document_type_first,
            document_linked_second, document_type_second,
        )
        return [self._serialize(r) for r in rows]

    def get_by_id(self, link_id: str) -> dict:
        row = self.repo.get_by_id(link_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
        return self._serialize(row)

    def get_by_document(self, document_id: str) -> list[dict]:
        return [self._serialize(r) for r in self.repo.get_by_document(document_id)]

    def create(self, payload: DocumentsLinkCreate, created_by: str) -> dict:
        data = payload.model_dump()
        data["created_by"] = created_by
        row = self.repo.create(data)
        return self._serialize(row)

    def update(self, link_id: str, payload: DocumentsLinkUpdate) -> dict:
        row = self.repo.get_by_id(link_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
        updates = payload.model_dump(exclude_unset=True)
        for key, value in updates.items():
            setattr(row, key, value)
        updated = self.repo.save(row)
        return self._serialize(updated)

    def delete(self, link_id: str) -> None:
        row = self.repo.get_by_id(link_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
        self.repo.delete(row)

    def _resolve_document(self, doc_id: str, doc_type: str) -> dict:
        if doc_type == "letter":
            row = self.repo.db.query(Letter).filter(Letter.id == int(doc_id)).first()
            if not row:
                return {"raw_id": doc_id}
            prefix = "Исходящее письмо" if row.type == "outgoing" else "Входящее письмо"
            parts = [prefix]
            if row.name:
                parts.append(row.name)
            if row.num:
                parts.append(f"№ {row.num}")
            return {
                "id": row.id,
                "type": row.type,
                "type_label": "Исходящее" if row.type == "outgoing" else "Входящее",
                "name": row.name,
                "num": row.num,
                "display_name": " ".join(parts),
            }

        if doc_type == "contract":
            row = self.repo.db.query(Contract).filter(Contract.id == int(doc_id)).first()
            if not row:
                return {"raw_id": doc_id}
            doc_type_name = ""
            if row.document_type_id:
                from app.repositories.contract_repository import ContractRepository
                cr = ContractRepository(self.repo.db)
                dt = cr.get_document_type_by_id(row.document_type_id)
                if dt:
                    doc_type_name = dt.name
            full_name = " ".join(part for part in [doc_type_name, row.name, "№", row.num] if part).strip()
            return {
                "id": row.id,
                "full_name": full_name,
                "type": row.type,
            }

        if doc_type == "file_letter":
            row = self.repo.db.query(LetterFile).filter(LetterFile.id == doc_id).first()
            if not row:
                return {"raw_id": doc_id}
            return {
                "id": row.id,
                "original_name": row.original_name,
                "type": row.type,
            }

        if doc_type == "file_contract":
            row = self.repo.db.query(ContractFile).filter(ContractFile.id == doc_id).first()
            if not row:
                return {"raw_id": doc_id}
            return {
                "id": row.id,
                "original_name": row.original_name,
                "type": row.type,
            }

        return {"raw_id": doc_id}

    def _serialize(self, row: DocumentsLink) -> dict:
        first = self._resolve_document(row.document_linked_first, row.document_type_first)
        second = self._resolve_document(row.document_linked_second, row.document_type_second)
        return {
            "id": row.id,
            "document_linked_first": row.document_linked_first,
            "document_type_first": row.document_type_first,
            "document_first": first,
            "document_linked_second": row.document_linked_second,
            "document_type_second": row.document_type_second,
            "document_second": second,
            "created_at": row.created_at,
            "created_by": row.created_by,
        }
