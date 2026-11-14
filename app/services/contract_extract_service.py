import uuid
from datetime import date

from fastapi import HTTPException, status

from app.models.contract_extract import (
    ContractExtract,
    ContractExtractCreate,
    ContractExtractMatchAllRequest,
    ContractExtractUpdate,
)
from app.repositories.contract_extract_repository import ContractExtractRepository
from app.repositories.contract_repository import ContractRepository
from app.repositories.extract_item_repository import ExtractItemRepository
from app.services.contract_extract_ai import extract_contract_reference


class ContractExtractService:
    def __init__(
        self,
        repo: ContractExtractRepository,
        contract_repo: ContractRepository,
        extract_item_repo: ExtractItemRepository,
    ) -> None:
        self.repo = repo
        self.contract_repo = contract_repo
        self.extract_item_repo = extract_item_repo

    @staticmethod
    def _serialize(row: ContractExtract) -> dict:
        return {
            "id": row.id,
            "contract_id": row.contract_id,
            "extract_id": row.extract_id,
        }

    @staticmethod
    def _parse_date(value: str | None) -> date | None:
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None

    def _match_one_extract_item(self, extract_item) -> dict:
        """Runs the AI extraction for a single extract_items row and, if a contract is
        found, creates the contract_extracts link. Never raises for "no match found" -
        only for infrastructure errors (Mistral unreachable, DB, etc.)."""
        result = {
            "extract_id": extract_item.id,
            "is_contract_payment": False,
            "contract_num": None,
            "contract_date": None,
            "contract_id": None,
            "matched": False,
            "reason": None,
        }

        ai = extract_contract_reference(extract_item.paymentPurpose or "")
        result["is_contract_payment"] = ai["is_contract_payment"]
        result["contract_num"] = ai["contract_num"]
        result["contract_date"] = ai["contract_date"]

        if not ai["is_contract_payment"] or not ai["contract_num"] or not ai["contract_date"]:
            result["reason"] = "not_a_contract_payment"
            return result

        contract_date = self._parse_date(ai["contract_date"])
        if not contract_date:
            result["reason"] = "invalid_contract_date"
            return result

        contract = self.contract_repo.get_contract_by_num_and_date(ai["contract_num"], contract_date)
        if not contract:
            result["reason"] = "contract_not_found"
            return result

        existing_link = self.repo.get_by_extract_id(extract_item.id)
        if existing_link:
            result["contract_id"] = existing_link.contract_id
            result["matched"] = True
            result["reason"] = "already_linked"
            return result

        row = ContractExtract(id=str(uuid.uuid4()), contract_id=contract.id, extract_id=extract_item.id)
        self.repo.create(row)

        result["contract_id"] = contract.id
        result["matched"] = True
        return result

    def match_extract_item(self, extract_id: str) -> dict:
        extract_item = self.extract_item_repo.get_by_id(extract_id)
        if not extract_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extract item not found")
        return self._match_one_extract_item(extract_item)

    def match_all(self, payload: ContractExtractMatchAllRequest) -> dict:
        if payload.extract_ids:
            items = self.extract_item_repo.get_by_ids(payload.extract_ids)
            found_ids = {item.id for item in items}
            missing_ids = [eid for eid in payload.extract_ids if eid not in found_ids]
        else:
            items = self.repo.get_unmatched_extract_items(payload.limit, payload.date_from, payload.date_to)
            missing_ids = []

        results = [self._match_one_extract_item(item) for item in items]
        matched = sum(1 for r in results if r["matched"])
        return {
            "processed": len(results),
            "matched": matched,
            "not_matched": len(results) - matched,
            "missing_extract_ids": missing_ids,
            "results": results,
        }

    def get_list(self, contract_id: int | None = None, extract_id: str | None = None, limit: int = 50, offset: int = 0) -> list[dict]:
        rows = self.repo.get_list(contract_id, extract_id, limit, offset)
        return [self._serialize(row) for row in rows]

    def get_by_id(self, item_id: str) -> dict:
        row = self.repo.get_by_id(item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
        return self._serialize(row)

    def create_manual(self, payload: ContractExtractCreate) -> dict:
        contract = self.contract_repo.get_contract_by_id(payload.contract_id)
        if not contract:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")

        extract_item = self.extract_item_repo.get_by_id(payload.extract_id)
        if not extract_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extract item not found")

        existing = self.repo.get_by_extract_id(payload.extract_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Эта строка выписки уже привязана к договору {existing.contract_id} (link id={existing.id}); используйте PATCH, чтобы изменить",
            )

        row = ContractExtract(id=str(uuid.uuid4()), contract_id=payload.contract_id, extract_id=payload.extract_id)
        created = self.repo.create(row)
        return self._serialize(created)

    def update_manual(self, item_id: str, payload: ContractExtractUpdate) -> dict:
        row = self.repo.get_by_id(item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")

        contract = self.contract_repo.get_contract_by_id(payload.contract_id)
        if not contract:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")

        row.contract_id = payload.contract_id
        updated = self.repo.save(row)
        return self._serialize(updated)

    def delete(self, item_id: str) -> None:
        row = self.repo.get_by_id(item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
        self.repo.delete(row)
