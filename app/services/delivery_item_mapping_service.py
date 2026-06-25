from __future__ import annotations

import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException, status

from app.models.delivery_item_mapping import (
    DeliveryItemMappingAutoMatchRequest,
    DeliveryItemMappingCreate,
    DeliveryItemMappingUpdate,
)
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.delivery_item_mapping_repository import DeliveryItemMappingRepository


class DeliveryItemMappingService:
    def __init__(
        self,
        repo: DeliveryItemMappingRepository,
        auth_user_repo: AuthUserRepository,
    ) -> None:
        self.repo = repo
        self.auth_user_repo = auth_user_repo

    def list(
        self,
        delivery_id: str | None = None,
        delivery_item_id: str | None = None,
        nomenclature_id: str | None = None,
    ):
        rows = self.repo.list_mappings(
            delivery_id=delivery_id,
            delivery_item_id=delivery_item_id,
            nomenclature_id=nomenclature_id,
        )
        return self._serialize(rows)

    def get_by_id(self, mapping_id: str):
        row = self.repo.get_by_id(mapping_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery item mapping not found")
        return self._serialize([row])[0]

    def create(self, payload: DeliveryItemMappingCreate, user_id: str):
        data = self._normalize_payload(payload.model_dump(exclude_unset=True))
        self._validate_links(
            delivery_id=data.get("delivery_id"),
            delivery_item_id=data.get("delivery_item_id"),
        )
        data["created_by"] = user_id
        created = self.repo.create(data)
        return self._serialize([created])[0]

    def update(self, mapping_id: str, payload: DeliveryItemMappingUpdate):
        row = self.repo.get_by_id(mapping_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery item mapping not found")
        data = self._normalize_payload(payload.model_dump(exclude_unset=True))
        self._validate_links(
            delivery_id=data.get("delivery_id", row.delivery_id),
            delivery_item_id=data.get("delivery_item_id", row.delivery_item_id),
        )
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save(row)
        return self._serialize([updated])[0]

    def delete(self, mapping_id: str):
        row = self.repo.get_by_id(mapping_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery item mapping not found")
        self.repo.delete(row)
        return None

    def auto_match(self, payload: DeliveryItemMappingAutoMatchRequest, user_id: str):
        delivery_items = self.repo.get_delivery_items(payload.delivery_id)
        if not delivery_items:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery items not found")

        nomenclature_rows = self.repo.get_all_nomenclature()
        if not nomenclature_rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nomenclature not found")

        delivery_payload = [
            {
                "id": item.id,
                "name": item.name,
                "unit_name": item.unit_name,
                "quantity": item.quantity,
            }
            for item in delivery_items
        ]
        nomenclature_payload = [
            {
                "id": row.id,
                "name": row.name,
                "article": row.article,
                "unit_id": row.unit_id,
            }
            for row in nomenclature_rows
        ]

        matches = self._call_mistral_for_matches(delivery_payload, nomenclature_payload)
        if not matches:
            return {
                "status": "success",
                "delivery_id": payload.delivery_id,
                "created_count": 0,
                "items": [],
            }

        self.repo.delete_by_delivery(payload.delivery_id)

        delivery_lookup = {str(item.id): item for item in delivery_items}
        nomenclature_lookup = {str(item.id): item for item in nomenclature_rows}

        created = []
        seen_delivery_item_ids = set()
        group_number = 1
        for match in matches:
            delivery_item_id = str(match.get("delivery_item_id", "")).strip()
            nomenclature_id = str(match.get("nomenclature_id", "")).strip()
            if not delivery_item_id or not nomenclature_id:
                continue
            if delivery_item_id in seen_delivery_item_ids:
                continue
            delivery_item = delivery_lookup.get(delivery_item_id)
            nomenclature = nomenclature_lookup.get(nomenclature_id)
            if not delivery_item or not nomenclature:
                continue

            seen_delivery_item_ids.add(delivery_item_id)
            row = self.repo.create_no_commit(
                {
                    "delivery_id": payload.delivery_id,
                    "delivery_item_id": delivery_item_id,
                    "nomenclature_id": nomenclature_id,
                    "delivery_quantity": delivery_item.quantity,
                    "nomenclature_quantity": delivery_item.quantity,
                    "group_number": group_number,
                    "created_by": user_id,
                }
            )
            created.append(row)
            group_number += 1

        self.repo.commit()
        return {
            "status": "success",
            "delivery_id": payload.delivery_id,
            "created_count": len(created),
            "items": self._serialize(created),
        }

    def _serialize(self, rows):
        if not rows:
            return []
        nomenclature = self.repo.get_nomenclature([row.nomenclature_id for row in rows if row.nomenclature_id])
        delivery_items = {
            row.delivery_item_id: self.repo.get_delivery_item_by_id(row.delivery_item_id)
            for row in rows
            if row.delivery_item_id
        }
        users = self.auth_user_repo.get_by_ids([row.created_by for row in rows if row.created_by])
        users_by_id = {user.id: user for user in users}
        return [
            {
                "id": row.id,
                "delivery_id": row.delivery_id,
                "delivery_item_id": row.delivery_item_id,
                "nomenclature_id": row.nomenclature_id,
                "nomenclature_name": nomenclature.get(row.nomenclature_id).name if nomenclature.get(row.nomenclature_id) else None,
                "delivery_at": row.delivery_at,
                "delivery_quantity": row.delivery_quantity,
                "nomenclature_quantity": row.nomenclature_quantity,
                "group_number": row.group_number,
                "created_at": row.created_at,
                "created_by": row.created_by,
                "created_by_user": self._map_user(users_by_id.get(row.created_by)),
                "delivery_item": self._serialize_delivery_item(delivery_items.get(row.delivery_item_id)),
            }
            for row in rows
        ]

    @staticmethod
    def _serialize_delivery_item(row):
        if not row:
            return None
        return {
            "id": row.id,
            "delivery_id": row.delivery_id,
            "nomenclature_id": row.nomenclature_id,
            "request_item_id": row.request_item_id,
            "invoice_item_id": row.invoice_item_id,
            "name": row.name,
            "unit_name": row.unit_name,
            "quantity": row.quantity,
        }

    def _validate_links(self, delivery_id: str | None, delivery_item_id: str | None) -> None:
        delivery_item = self.repo.get_delivery_item_by_id(delivery_item_id or "")
        if not delivery_item:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Delivery item not found")
        if delivery_id and delivery_item.delivery_id != delivery_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="delivery_item_id does not belong to delivery_id",
            )

    @staticmethod
    def _normalize_payload(data: dict) -> dict:
        normalized = dict(data)
        if normalized.get("nomenclature_id") == "":
            normalized["nomenclature_id"] = None
        return normalized

    def _call_mistral_for_matches(self, delivery_items: list[dict], nomenclature_items: list[dict]) -> list[dict]:
        mistral_api_key = os.getenv("MISTRAL_API_KEY")
        if not mistral_api_key:
            project_root = Path(__file__).resolve().parents[2]
            load_dotenv(project_root / ".env", override=True)
            mistral_api_key = os.getenv("MISTRAL_API_KEY")
        if not mistral_api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="MISTRAL_API_KEY is not set",
            )

        try:
            from mistralai import Mistral
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="mistralai package is not installed",
            ) from exc

        prompt = (
            "Match delivery items to nomenclature items.\n"
            "Rules:\n"
            "- match by semantic name similarity and article hints when available.\n"
            "- for each delivery item choose the most likely nomenclature.\n"
            "- return only confident matches.\n"
            "Return ONLY JSON array like:\n"
            '[{"delivery_item_id":"...","nomenclature_id":"..."}]\n'
            f"Delivery items: {json.dumps(delivery_items, ensure_ascii=False)}\n"
            f"Nomenclature items: {json.dumps(nomenclature_items, ensure_ascii=False)}"
        )

        client = Mistral(api_key=mistral_api_key)
        response = client.chat.complete(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.choices[0].message.content
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        return self._extract_matches_json(str(content))

    @staticmethod
    def _extract_matches_json(content: str) -> list[dict]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        parsed = None
        try:
            parsed = json.loads(cleaned)
        except Exception:
            match = re.search(r"\[.*\]", cleaned, flags=re.S)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                except Exception:
                    parsed = None

        if not isinstance(parsed, list):
            return []
        return [item for item in parsed if isinstance(item, dict)]

    @staticmethod
    def _map_user(user):
        if not user:
            return None
        name_initial = f"{user.name[0]}." if user.name else ""
        patronymic_initial = f"{user.patronymic[0]}." if user.patronymic else ""
        short_fio = " ".join(part for part in [user.surname, name_initial, patronymic_initial] if part).strip()
        return {
            "id": user.id,
            "name": user.name,
            "surname": user.surname,
            "patronymic": user.patronymic,
            "short_fio": short_fio,
        }
