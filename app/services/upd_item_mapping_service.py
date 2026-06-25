from __future__ import annotations

import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException, status

from app.models.upd_item_mapping import (
    UpdItemMappingAutoMatchRequest,
    UpdItemMappingCreate,
    UpdItemMappingUpdate,
)
from app.repositories.upd_item_mapping_repository import UpdItemMappingRepository


class UpdItemMappingService:
    def __init__(self, repo: UpdItemMappingRepository) -> None:
        self.repo = repo

    def list(
        self,
        upd_documents_id: str | None = None,
        upd_documents_item_id: str | None = None,
        nomenclature_id: str | None = None,
    ):
        rows = self.repo.list_mappings(
            upd_documents_id=upd_documents_id,
            upd_documents_item_id=upd_documents_item_id,
            nomenclature_id=nomenclature_id,
        )
        warehouse_names = self.repo.get_warehouse_names(
            [mapping.warehouse_id for mapping, _, _ in rows if mapping.warehouse_id]
        )
        unit_names = self.repo.get_unit_names(
            [nomenclature.unit_id for _, _, nomenclature in rows if nomenclature and nomenclature.unit_id]
        )
        return [
            self._to_response(mapping, document_item, nomenclature, warehouse_names, unit_names)
            for mapping, document_item, nomenclature in rows
        ]

    def get_by_id(self, mapping_id: str):
        mapping = self.repo.get_mapping_by_id(mapping_id)
        if not mapping:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UPD item mapping not found")
        document_item = self.repo.get_document_item_by_id(mapping.upd_documents_item_id or "")
        nomenclature = self.repo.get_nomenclature_by_id(mapping.nomenclature_id or "")
        warehouse_names = self.repo.get_warehouse_names([mapping.warehouse_id] if mapping.warehouse_id else [])
        unit_names = self.repo.get_unit_names([nomenclature.unit_id] if nomenclature and nomenclature.unit_id else [])
        return self._to_response(mapping, document_item, nomenclature, warehouse_names, unit_names)

    def create(self, payload: UpdItemMappingCreate):
        data = payload.model_dump(exclude_unset=True)
        document_row, document_item, nomenclature = self._validate_links(
            upd_documents_id=data.get("upd_documents_id"),
            upd_documents_item_id=data.get("upd_documents_item_id"),
            nomenclature_id=data.get("nomenclature_id"),
        )
        data["upd_documents_id"] = document_row.id
        data["upd_documents_item_id"] = document_item.id
        created = self.repo.create_mapping(data)
        warehouse_names = self.repo.get_warehouse_names([created.warehouse_id] if created.warehouse_id else [])
        unit_names = self.repo.get_unit_names([nomenclature.unit_id] if nomenclature and nomenclature.unit_id else [])
        return self._to_response(created, document_item, nomenclature, warehouse_names, unit_names)

    def update(self, mapping_id: str, payload: UpdItemMappingUpdate):
        mapping = self.repo.get_mapping_by_id(mapping_id)
        if not mapping:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UPD item mapping not found")

        data = payload.model_dump(exclude_unset=True)
        document_row, document_item, nomenclature = self._validate_links(
            upd_documents_id=data.get("upd_documents_id", mapping.upd_documents_id),
            upd_documents_item_id=data.get("upd_documents_item_id", mapping.upd_documents_item_id),
            nomenclature_id=data.get("nomenclature_id", mapping.nomenclature_id),
        )
        data["upd_documents_id"] = document_row.id
        data["upd_documents_item_id"] = document_item.id

        for key, value in data.items():
            setattr(mapping, key, value)

        updated = self.repo.save_mapping(mapping)
        warehouse_names = self.repo.get_warehouse_names([updated.warehouse_id] if updated.warehouse_id else [])
        unit_names = self.repo.get_unit_names([nomenclature.unit_id] if nomenclature and nomenclature.unit_id else [])
        return self._to_response(updated, document_item, nomenclature, warehouse_names, unit_names)

    def delete(self, mapping_id: str):
        mapping = self.repo.get_mapping_by_id(mapping_id)
        if not mapping:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UPD item mapping not found")
        self.repo.delete_mapping(mapping)
        return None

    def auto_match(self, payload: UpdItemMappingAutoMatchRequest):
        document = self.repo.get_document_by_id(payload.upd_documents_id)
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UPD document not found")

        document_items = self.repo.get_document_items(payload.upd_documents_id)
        if not document_items:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UPD document items not found")

        nomenclature_rows = self.repo.get_all_nomenclature()
        if not nomenclature_rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nomenclature not found")

        document_payload = [
            {
                "id": item.id,
                "name": item.name,
                "unit_name": item.unit_name,
                "quantity": item.quantity,
                "price": item.price,
                "sum": item.sum,
            }
            for item in document_items
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

        matches = self._call_mistral_for_matches(document_payload, nomenclature_payload)
        if not matches:
            return {
                "status": "success",
                "upd_documents_id": payload.upd_documents_id,
                "created_count": 0,
                "items": [],
            }

        self.repo.delete_by_document(payload.upd_documents_id)

        document_lookup = {str(item["id"]): item for item in document_payload}
        nomenclature_lookup = {str(item["id"]): item for item in nomenclature_payload}
        document_row_lookup = {item.id: item for item in document_items}
        nomenclature_row_lookup = {row.id: row for row in nomenclature_rows}

        created = []
        seen_document_item_ids = set()
        group_number = 1
        for match in matches:
            document_item_id = str(match.get("upd_documents_item_id", "")).strip()
            nomenclature_id = str(match.get("nomenclature_id", "")).strip()
            if not document_item_id or not nomenclature_id:
                continue
            if document_item_id in seen_document_item_ids:
                continue
            document_item = document_lookup.get(document_item_id)
            nomenclature = nomenclature_lookup.get(nomenclature_id)
            document_item_row = document_row_lookup.get(document_item_id)
            nomenclature_row = nomenclature_row_lookup.get(nomenclature_id)
            if not document_item or not nomenclature or not document_item_row or not nomenclature_row:
                continue

            seen_document_item_ids.add(document_item_id)

            row = self.repo.create_mapping_no_commit(
                {
                    "upd_documents_id": payload.upd_documents_id,
                    "upd_documents_item_id": document_item_id,
                    "nomenclature_id": nomenclature_id,
                    "group_number": group_number,
                    "match_type": "direct",
                    "mapped_quantity": document_item_row.quantity,
                    "object_id": payload.object_id,
                    "price": document_item_row.price,
                    "warehouse_id": payload.warehouse_id or document.warehouse_id,
                    "attribute": payload.attribute or "Закупка",
                }
            )
            created.append((row, document_item_row, nomenclature_row))
            group_number += 1

        self.repo.commit()
        warehouse_names = self.repo.get_warehouse_names(
            [row.warehouse_id for row, _, _ in created if row.warehouse_id]
        )
        unit_names = self.repo.get_unit_names(
            [nomenclature.unit_id for _, _, nomenclature in created if nomenclature and nomenclature.unit_id]
        )

        return {
            "status": "success",
            "upd_documents_id": payload.upd_documents_id,
            "created_count": len(created),
            "items": [
                self._to_response(row, document_item, nomenclature, warehouse_names, unit_names)
                for row, document_item, nomenclature in created
            ],
        }

    def _validate_links(
        self,
        upd_documents_id: str | None,
        upd_documents_item_id: str | None,
        nomenclature_id: str | None,
    ):
        document_row = self.repo.get_document_by_id(upd_documents_id or "")
        if not document_row:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="UPD document not found")

        document_item = self.repo.get_document_item_by_id(upd_documents_item_id or "")
        if not document_item:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="UPD document item not found")
        if document_item.upd_documents_id != document_row.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="upd_documents_item_id does not belong to upd_documents_id",
            )

        nomenclature = self.repo.get_nomenclature_by_id(nomenclature_id or "")
        if not nomenclature:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nomenclature not found")

        return document_row, document_item, nomenclature

    def _to_response(
        self,
        mapping,
        document_item,
        nomenclature,
        warehouse_names: dict[str, str] | None = None,
        unit_names: dict[str, str] | None = None,
    ):
        warehouse_names = warehouse_names or {}
        unit_names = unit_names or {}
        return {
            "id": mapping.id,
            "upd_documents_id": mapping.upd_documents_id,
            "upd_documents_item_id": mapping.upd_documents_item_id,
            "nomenclature_id": mapping.nomenclature_id,
            "group_number": mapping.group_number,
            "match_type": mapping.match_type,
            "mapped_quantity": mapping.mapped_quantity,
            "object_id": mapping.object_id,
            "price": mapping.price,
            "warehouse_id": mapping.warehouse_id,
            "warehouse_name": warehouse_names.get(mapping.warehouse_id) if mapping.warehouse_id else None,
            "attribute": mapping.attribute,
            "created_at": mapping.created_at,
            "upd_document_item": {
                "id": document_item.id,
                "upd_documents_id": document_item.upd_documents_id,
                "name": document_item.name,
                "unit_name": document_item.unit_name,
                "quantity": document_item.quantity,
                "price": document_item.price,
                "sum": document_item.sum,
            } if document_item else None,
            "nomenclature": {
                "id": nomenclature.id,
                "name": nomenclature.name,
                "article": nomenclature.article,
                "unit_id": nomenclature.unit_id,
                "unit_name": unit_names.get(nomenclature.unit_id) if nomenclature.unit_id else None,
            } if nomenclature else None,
        }

    def _call_mistral_for_matches(self, upd_items: list[dict], nomenclature_items: list[dict]) -> list[dict]:
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
            "Match UPD document items to nomenclature items.\n"
            "Rules:\n"
            "- match by semantic name similarity, article hints, and unit consistency when available.\n"
            "- each UPD item can be used once.\n"
            "- each nomenclature item can be used multiple times only if it is clearly the same product; otherwise prefer one-to-one confident matches.\n"
            "- return only confident matches.\n"
            "Return ONLY JSON array like:\n"
            '[{"upd_documents_item_id":"...","nomenclature_id":"..."}]\n'
            f"UPD items: {json.dumps(upd_items, ensure_ascii=False)}\n"
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
