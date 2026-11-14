import re
import uuid
from datetime import datetime

from fastapi import HTTPException, status

from app.models.business_card import (
    ExtractBusinessCard,
    ExtractBusinessCardCreate,
    ExtractBusinessCardMatchAllRequest,
    ExtractBusinessCardUpdate,
)
from app.repositories.business_card_repository import BusinessCardRepository
from app.repositories.extract_business_card_repository import ExtractBusinessCardRepository
from app.repositories.extract_item_repository import ExtractItemRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository

# Two formats seen in the wild:
# - Sberbank: "...по карте MIR 220220BFAFB19498 за 2026-09-30..." (scheme name, then the token)
# - Alfa-Bank: "...по чеку 27.09.26,16C8B1 по карте 220015++++++7517. MCC5814" (no scheme,
#   the masked number comes right after "карте", masked with "+")
# Capture up to two words after "карте": if the first one has no digits, it's a scheme name
# (MIR/VISA/...) and the real token is the second word.
CARD_AFTER_RE = re.compile(r"карте\s+(\S+)(?:\s+(\S+))?")


def extract_card_last4(payment_purpose: str | None) -> str | None:
    if not payment_purpose:
        return None
    match = CARD_AFTER_RE.search(payment_purpose)
    if not match:
        return None
    first, second = match.group(1), match.group(2)
    token = first if any(ch.isdigit() for ch in first) else second
    if not token:
        return None
    digits_and_letters = re.sub(r"[^0-9A-Za-z]", "", token)
    return digits_and_letters[-4:] if len(digits_and_letters) >= 4 else None


class ExtractBusinessCardService:
    def __init__(
        self,
        repo: ExtractBusinessCardRepository,
        business_card_repo: BusinessCardRepository,
        extract_item_repo: ExtractItemRepository,
        reference_repo: ReferenceObjectRepository | None = None,
    ) -> None:
        self.repo = repo
        self.business_card_repo = business_card_repo
        self.extract_item_repo = extract_item_repo
        self.reference_repo = reference_repo

    def _object_short_name(self, object_id: str | None) -> str | None:
        if not object_id or not self.reference_repo:
            return None
        objects = self.reference_repo.get_objects_by_ids([object_id])
        return objects[0].short_name if objects else None

    def _serialize(self, row: ExtractBusinessCard, card=None) -> dict:
        return {
            "id": row.id,
            "extract_id": row.extract_id,
            "business_card_id": row.business_card_id,
            "card_number_mask": card.card_number_mask if card else None,
            "card_last4": card.card_last4 if card else None,
            "holder_name": card.holder_name if card else None,
            "object_id": row.object_id,
            "object_short_name": self._object_short_name(row.object_id),
            "created_at": row.created_at,
        }

    def _match_one_extract_item(self, extract_item, created_by: str) -> dict:
        result = {
            "extract_id": extract_item.id,
            "card_last4": None,
            "business_card_id": None,
            "matched": False,
            "reason": None,
            "candidates": [],
        }

        last4 = extract_card_last4(extract_item.paymentPurpose)
        result["card_last4"] = last4

        if not last4:
            result["reason"] = "card_reference_not_found_in_text"
            return result

        candidates = self.business_card_repo.get_active_by_last4(last4)
        if not candidates:
            result["reason"] = "card_not_found"
            return result

        if len(candidates) > 1:
            result["reason"] = "ambiguous_match"
            result["candidates"] = [c.id for c in candidates]
            return result

        card = candidates[0]

        existing_link = self.repo.get_by_extract_id(extract_item.id)
        if existing_link:
            result["business_card_id"] = existing_link.business_card_id
            result["matched"] = True
            result["reason"] = "already_linked"
            return result

        row = ExtractBusinessCard(
            id=str(uuid.uuid4()),
            extract_id=extract_item.id,
            business_card_id=card.id,
            created_by=created_by,
        )
        self.repo.create(row)

        result["business_card_id"] = card.id
        result["matched"] = True
        return result

    def match_extract_item(self, extract_id: str, user_id: str) -> dict:
        extract_item = self.extract_item_repo.get_by_id(extract_id)
        if not extract_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extract item not found")
        return self._match_one_extract_item(extract_item, user_id)

    def match_all(self, payload: ExtractBusinessCardMatchAllRequest, user_id: str) -> dict:
        if payload.extract_ids:
            items = self.extract_item_repo.get_by_ids(payload.extract_ids)
            found_ids = {item.id for item in items}
            missing_ids = [eid for eid in payload.extract_ids if eid not in found_ids]
        else:
            items = self.repo.get_unmatched_extract_items(payload.limit, payload.date_from, payload.date_to)
            missing_ids = []

        results = [self._match_one_extract_item(item, user_id) for item in items]
        matched = sum(1 for r in results if r["matched"])
        return {
            "processed": len(results),
            "matched": matched,
            "not_matched": len(results) - matched,
            "missing_extract_ids": missing_ids,
            "results": results,
        }

    def get_list(
        self,
        business_card_id: str | None = None,
        extract_id: str | None = None,
        object_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        rows = self.repo.get_list(business_card_id, extract_id, object_id, limit, offset)
        cards_by_id = {c.id: c for c in self.business_card_repo.get_by_ids([r.business_card_id for r in rows])}
        return [self._serialize(row, cards_by_id.get(row.business_card_id)) for row in rows]

    def get_by_id(self, item_id: str) -> dict:
        row = self.repo.get_by_id(item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
        card = self.business_card_repo.get_by_id(row.business_card_id)
        return self._serialize(row, card)

    def get_by_object(
        self,
        object_id: str,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict:
        rows = self.repo.get_rows_by_object_id(object_id, date_from, date_to)

        card_ids = list({link.business_card_id for link, _item in rows})
        cards_by_id = {c.id: c for c in self.business_card_repo.get_by_ids(card_ids)}

        total_debit = sum(float(item.amount or 0) for _link, item in rows if item.direction == "DEBIT")
        total_credit = sum(float(item.amount or 0) for _link, item in rows if item.direction == "CREDIT")

        operations = []
        for link, item in rows:
            card = cards_by_id.get(link.business_card_id)
            operations.append(
                {
                    "extract_business_card_id": link.id,
                    "extract_id": item.id,
                    "business_card_id": link.business_card_id,
                    "card_number_mask": card.card_number_mask if card else None,
                    "card_last4": card.card_last4 if card else None,
                    "holder_name": card.holder_name if card else None,
                    "bank_type": card.bank_type if card else None,
                    "operationDate": item.operationDate,
                    "amount": float(item.amount) if item.amount is not None else None,
                    "direction": item.direction,
                    "paymentPurpose": item.paymentPurpose,
                    "payeeName": item.payeeName,
                    "payerName": item.payerName,
                }
            )

        return {
            "object_id": object_id,
            "object_short_name": self._object_short_name(object_id),
            "period": {"date_from": date_from, "date_to": date_to},
            "summary": {
                "total_debit": total_debit,
                "total_credit": total_credit,
                "net_spent": total_debit - total_credit,
                "operations_count": len(rows),
            },
            "operations": operations,
        }

    def create_manual(self, payload: ExtractBusinessCardCreate, created_by: str) -> dict:
        card = self.business_card_repo.get_by_id(payload.business_card_id)
        if not card:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business card not found")

        extract_item = self.extract_item_repo.get_by_id(payload.extract_id)
        if not extract_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extract item not found")

        existing = self.repo.get_by_extract_id(payload.extract_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Эта строка выписки уже привязана к карте {existing.business_card_id} (link id={existing.id}); используйте PATCH, чтобы изменить",
            )

        row = ExtractBusinessCard(
            id=str(uuid.uuid4()),
            extract_id=payload.extract_id,
            business_card_id=payload.business_card_id,
            object_id=payload.object_id,
            created_by=created_by,
        )
        created = self.repo.create(row)
        return self._serialize(created, card)

    def update_manual(self, item_id: str, payload: ExtractBusinessCardUpdate) -> dict:
        row = self.repo.get_by_id(item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")

        data = payload.model_dump(exclude_unset=True, exclude={"clear_object"})

        if "business_card_id" in data:
            card = self.business_card_repo.get_by_id(data["business_card_id"])
            if not card:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business card not found")

        if payload.clear_object:
            row.object_id = None
            data.pop("object_id", None)

        for key, value in data.items():
            setattr(row, key, value)

        updated = self.repo.save(row)
        card = self.business_card_repo.get_by_id(updated.business_card_id)
        return self._serialize(updated, card)

    def delete(self, item_id: str) -> None:
        row = self.repo.get_by_id(item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
        self.repo.delete(row)
