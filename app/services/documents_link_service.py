from fastapi import HTTPException, status

from app.models.act import Act, ActType
from app.models.contract import Contract
from app.models.custom_registry import CustomRegistry, CustomRegistryField, CustomRegistryRecord, CustomRegistryValue
from app.models.documents_link import (
    DOCUMENT_TYPE_LABELS,
    FILE_DOCUMENT_TYPES,
    LINKABLE_DOCUMENT_TYPES,
    DocumentsLink,
    DocumentsLinkCreate,
    DocumentsLinkUpdate,
)
from app.models.invoice import Invoice
from app.models.upd_registry import UpdRegistry
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

    def get_by_document(self, document_id: str, document_type: str | None = None) -> list[dict]:
        return [self._serialize(r) for r in self.repo.get_by_document(document_id, document_type)]

    def get_types(self) -> list[dict]:
        return [{"type": t, "label": DOCUMENT_TYPE_LABELS[t]} for t in LINKABLE_DOCUMENT_TYPES]

    def get_for_document(self, document_type: str, document_id: str) -> dict:
        """Everything linked to one document: the other side of each link, ready to show."""
        self._check_type(document_type)
        if not self._exists(document_id, document_type):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Документ не найден")
        items = []
        for row in self.repo.get_by_document(str(document_id), document_type):
            mine_first = row.document_linked_first == str(document_id) and row.document_type_first == document_type
            other_id, other_type = (row.document_linked_second, row.document_type_second) if mine_first else (row.document_linked_first, row.document_type_first)
            other = self._resolve_document(other_id, other_type)
            items.append({
                "link_id": row.id, "document_type": other_type,
                "document_type_label": DOCUMENT_TYPE_LABELS.get(other_type), "document_id": other_id,
                "document": other, "display_name": other.get("display_name") or other.get("full_name") or other.get("original_name"),
                "created_at": row.created_at, "created_by": row.created_by,
            })
        return {"document_type": document_type, "document_id": str(document_id), "total": len(items), "items": items}

    def create(self, payload: DocumentsLinkCreate, created_by: str) -> dict:
        data = payload.model_dump()
        for side in ("first", "second"):
            data[f"document_linked_{side}"] = str(data[f"document_linked_{side}"]).strip()
            self._check_type(data[f"document_type_{side}"])
            if data[f"document_type_{side}"] in LINKABLE_DOCUMENT_TYPES and not self._exists(data[f"document_linked_{side}"], data[f"document_type_{side}"]):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                    detail=f"{DOCUMENT_TYPE_LABELS[data[f'document_type_{side}']]} {data[f'document_linked_{side}']} не найден")
        a = (data["document_linked_first"], data["document_type_first"])
        b = (data["document_linked_second"], data["document_type_second"])
        if a == b:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Нельзя связать документ с самим собой")
        existing = self.repo.find_pair(*a, *b)
        if existing:  # the same pair twice is not a new link
            return self._serialize(existing)
        data["created_by"] = created_by
        row = self.repo.create(data)
        return self._serialize(row)

    @staticmethod
    def _check_type(document_type: str) -> None:
        if document_type not in LINKABLE_DOCUMENT_TYPES and document_type not in FILE_DOCUMENT_TYPES:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail=f"Неизвестный тип документа «{document_type}». Допустимые: {', '.join(LINKABLE_DOCUMENT_TYPES + FILE_DOCUMENT_TYPES)}")

    def _exists(self, document_id: str, document_type: str) -> bool:
        if not str(document_id).isdigit():
            return False
        model = {"contract": Contract, "act": Act, "letter": Letter, "invoice": Invoice,
                 "upd": UpdRegistry, "registry_record": CustomRegistryRecord}[document_type]
        return self.repo.db.query(model.id).filter(model.id == int(document_id)).first() is not None

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
                "date": row.date,
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

        if doc_type == "act":
            if not str(doc_id).isdigit():
                return {"raw_id": doc_id}
            row = self.repo.db.query(Act).filter(Act.id == int(doc_id)).first()
            if not row:
                return {"raw_id": doc_id}
            act_type = self.repo.db.query(ActType).filter(ActType.id == row.act_type_id).first()
            type_name = act_type.name if act_type else ""
            return {
                "id": row.id,
                # same wording as "fullname" in the acts list
                "full_name": f"{type_name} №{row.num}".strip(),
                "act_type_name": type_name,
                "num": row.num,
                "date": row.date,
            }

        if doc_type == "invoice":
            if not str(doc_id).isdigit():
                return {"raw_id": doc_id}
            row = self.repo.db.query(Invoice).filter(Invoice.id == int(doc_id)).first()
            if not row:
                return {"raw_id": doc_id}
            label = "Исходящий счёт" if row.type == "outgoing" else "Счёт"
            return {
                "id": row.id, "type": row.type, "num": row.num, "date": row.date, "total_amount": row.total_amount,
                "display_name": f"{label} №{row.num}" if row.num else f"{label} #{row.id}",
            }

        if doc_type == "upd":
            if not str(doc_id).isdigit():
                return {"raw_id": doc_id}
            row = self.repo.db.query(UpdRegistry).filter(UpdRegistry.id == int(doc_id)).first()
            if not row:
                return {"raw_id": doc_id}
            return {
                "id": row.id, "num": row.num, "date": row.date, "sum": row.sum, "is_signed": bool(row.is_signed),
                "display_name": f"УПД №{row.num}" if row.num else f"УПД #{row.id}",
            }

        if doc_type == "registry_record":
            if not str(doc_id).isdigit():
                return {"raw_id": doc_id}
            record = self.repo.db.query(CustomRegistryRecord).filter(CustomRegistryRecord.id == int(doc_id)).first()
            if not record:
                return {"raw_id": doc_id}
            registry = self.repo.db.query(CustomRegistry).filter(CustomRegistry.id == record.registry_id).first()
            columns = (
                self.repo.db.query(CustomRegistryField.label, CustomRegistryValue.search_text)
                .join(CustomRegistryValue, CustomRegistryValue.field_id == CustomRegistryField.id)
                .filter(CustomRegistryValue.record_id == record.id, CustomRegistryField.show_in_list.is_(True))
                .order_by(CustomRegistryField.sort_order).all()
            )
            summary = "; ".join(f"{label}: {text}" for label, text in columns if text)
            name = registry.name if registry else "Реестр"
            return {
                "id": record.id, "registry_id": record.registry_id, "registry_name": name, "summary": summary or None,
                "display_name": f"{name} #{record.id}" + (f" ({summary})" if summary else ""),
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
