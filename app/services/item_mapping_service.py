from __future__ import annotations

import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException, status

from app.models.item_mapping import ItemMappingCreate, ItemMappingUpdate
from app.repositories.item_mapping_repository import ItemMappingRepository


class ItemMappingService:
    def __init__(self, repo: ItemMappingRepository) -> None:
        self.repo = repo

    def list(
        self,
        request_id: int | None = None,
        invoice_id: int | None = None,
        request_item_id: str | None = None,
        invoice_item_id: str | None = None,
    ):
        rows = self.repo.list_mappings(
            request_id=request_id,
            invoice_id=invoice_id,
            request_item_id=request_item_id,
            invoice_item_id=invoice_item_id,
        )
        unit_ids = [mapping.unit_id for mapping, _, _ in rows if mapping.unit_id]
        unit_names = self.repo.get_unit_names(unit_ids)
        return [
            self._to_response(mapping, request_item, invoice_item, unit_names)
            for mapping, request_item, invoice_item in rows
        ]

    def get_by_id(self, mapping_id: str):
        mapping = self.repo.get_mapping_by_id(mapping_id)
        if not mapping:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item mapping not found")

        request_item = self.repo.get_request_item_by_id(mapping.request_item_id)
        invoice_item = self.repo.get_invoice_item_by_id(mapping.invoice_item_id)
        unit_names = self.repo.get_unit_names([mapping.unit_id] if mapping.unit_id else [])
        return self._to_response(mapping, request_item, invoice_item, unit_names)

    def create(self, payload: ItemMappingCreate):
        data = payload.model_dump(exclude_unset=True)
        request_item, invoice_item = self._validate_and_resolve_links(
            request_item_id=data.get("request_item_id"),
            invoice_item_id=data.get("invoice_item_id"),
            request_id=data.get("request_id"),
            invoice_id=data.get("invoice_id"),
        )
        data["request_id"] = request_item.request_id
        data["invoice_id"] = invoice_item.invoice_id
        if "unit_id" not in data:
            data["unit_id"] = request_item.unit_id

        created = self.repo.create_mapping(data)
        unit_names = self.repo.get_unit_names([created.unit_id] if created.unit_id else [])
        return self._to_response(created, request_item, invoice_item, unit_names)

    def update(self, mapping_id: str, payload: ItemMappingUpdate):
        mapping = self.repo.get_mapping_by_id(mapping_id)
        if not mapping:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item mapping not found")

        data = payload.model_dump(exclude_unset=True)
        request_item_id = data.get("request_item_id", mapping.request_item_id)
        invoice_item_id = data.get("invoice_item_id", mapping.invoice_item_id)
        request_id = data.get("request_id", mapping.request_id)
        invoice_id = data.get("invoice_id", mapping.invoice_id)

        request_item, invoice_item = self._validate_and_resolve_links(
            request_item_id=request_item_id,
            invoice_item_id=invoice_item_id,
            request_id=request_id,
            invoice_id=invoice_id,
        )
        data["request_id"] = request_item.request_id
        data["invoice_id"] = invoice_item.invoice_id
        if "unit_id" not in data:
            data["unit_id"] = request_item.unit_id

        for key, value in data.items():
            setattr(mapping, key, value)

        updated = self.repo.save_mapping(mapping)
        unit_names = self.repo.get_unit_names([updated.unit_id] if updated.unit_id else [])
        return self._to_response(updated, request_item, invoice_item, unit_names)

    def delete(self, mapping_id: str):
        mapping = self.repo.get_mapping_by_id(mapping_id)
        if not mapping:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item mapping not found")
        self.repo.delete_mapping(mapping)
        return None

    def auto_match(self, request_id: int, invoice_id: int):
        request_rows = self.repo.get_request_items_for_matching(request_id)
        invoice_items = self.repo.get_invoice_items_for_matching(invoice_id)

        if not request_rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request items not found")
        if not invoice_items:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice items not found")

        request_payload = [
            {
                "id": request_item.id,
                "name": request_item.name,
                "quantity": request_item.quantity,
                "unit_name": unit.name if unit else None,
                "unit_id": request_item.unit_id,
            }
            for request_item, unit in request_rows
        ]
        invoice_payload = [
            {
                "id": invoice_item.id,
                "name": invoice_item.name,
                "unit_name": invoice_item.unit_name,
                "quantity": invoice_item.quantity,
            }
            for invoice_item in invoice_items
        ]

        matches = self._call_mistral_for_matches(request_payload, invoice_payload)
        if not matches:
            return {
                "status": "success",
                "request_id": request_id,
                "invoice_id": invoice_id,
                "created_count": 0,
                "items": [],
            }

        request_lookup = {str(item["id"]): item for item in request_payload}
        invoice_lookup = {str(item["id"]): item for item in invoice_payload}

        self.repo.delete_by_request_invoice(request_id, invoice_id)

        created = []
        seen_request_ids = set()
        seen_invoice_ids = set()
        group_number = 1
        for match in matches:
            request_item_id = str(match.get("request_item_id", "")).strip()
            invoice_item_id = str(match.get("invoice_item_id", "")).strip()
            if not request_item_id or not invoice_item_id:
                continue
            if request_item_id in seen_request_ids or invoice_item_id in seen_invoice_ids:
                continue
            request_item = request_lookup.get(request_item_id)
            invoice_item = invoice_lookup.get(invoice_item_id)
            if not request_item or not invoice_item:
                continue

            seen_request_ids.add(request_item_id)
            seen_invoice_ids.add(invoice_item_id)

            row = self.repo.create_mapping_no_commit(
                {
                    "request_id": request_id,
                    "invoice_id": invoice_id,
                    "request_item_id": request_item_id,
                    "invoice_item_id": invoice_item_id,
                    "group_number": group_number,
                    "match_type": "direct",
                    "mapped_quantity": request_item.get("quantity") or 0,
                    "unit_id": request_item.get("unit_id"),
                }
            )
            created.append(row)
            group_number += 1

        self.repo.commit()

        created_payload = []
        unit_names = self.repo.get_unit_names(
            [item.unit_id for item in created if item.unit_id]
        )
        for row in created:
            request_item = self.repo.get_request_item_by_id(row.request_item_id)
            invoice_item = self.repo.get_invoice_item_by_id(row.invoice_item_id)
            created_payload.append(self._to_response(row, request_item, invoice_item, unit_names))

        return {
            "status": "success",
            "request_id": request_id,
            "invoice_id": invoice_id,
            "created_count": len(created_payload),
            "items": created_payload,
        }

    def _validate_and_resolve_links(
        self,
        request_item_id: str | None,
        invoice_item_id: str | None,
        request_id: int | None,
        invoice_id: int | None,
    ):
        request_item = self.repo.get_request_item_by_id(request_item_id or "")
        if not request_item:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request item not found")

        invoice_item = self.repo.get_invoice_item_by_id(invoice_item_id or "")
        if not invoice_item:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invoice item not found")

        if request_id is not None and request_id != request_item.request_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="request_id does not match request_item_id",
            )
        if invoice_id is not None and invoice_id != invoice_item.invoice_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="invoice_id does not match invoice_item_id",
            )

        return request_item, invoice_item

    def _to_response(self, mapping, request_item, invoice_item, unit_names: dict[str, str] | None = None):
        unit_names = unit_names or {}
        mapped_quantity_sum = mapping.mapped_quantity if mapping.match_type == "sum" else None
        mapped_quantity_head = None
        if mapping.match_type == "kit_head":
            mapped_quantity_head = mapping.mapped_quantity
        elif mapping.match_type == "kit_component":
            mapped_quantity_head = self.repo.get_kit_head_quantity(
                request_id=mapping.request_id,
                invoice_id=mapping.invoice_id,
                group_number=mapping.group_number,
            )

        return {
            "id": mapping.id,
            "request_id": mapping.request_id,
            "invoice_id": mapping.invoice_id,
            "request_item_id": mapping.request_item_id,
            "invoice_item_id": mapping.invoice_item_id,
            "unit_id": mapping.unit_id,
            "unit_id_name": unit_names.get(mapping.unit_id) if mapping.unit_id else None,
            "group_number": mapping.group_number,
            "match_type": mapping.match_type,
            "mapped_quantity": mapping.mapped_quantity,
            "mapped_quantity_sum": mapped_quantity_sum,
            "mapped_quantity_head": mapped_quantity_head,
            "created_at": mapping.created_at,
            "request_item": {
                "id": request_item.id,
                "request_id": request_item.request_id,
                "num": request_item.num,
                "name": request_item.name,
                "unit_id": request_item.unit_id,
                "quantity": request_item.quantity,
                "comment": request_item.comment,
            }
            if request_item
            else None,
            "invoice_item": {
                "id": invoice_item.id,
                "invoice_id": invoice_item.invoice_id,
                "name": invoice_item.name,
                "unit_name": invoice_item.unit_name,
                "quantity": invoice_item.quantity,
                "price": invoice_item.price,
                "sum": invoice_item.sum,
            }
            if invoice_item
            else None,
        }

    def _call_mistral_for_matches(self, request_items: list[dict], invoice_items: list[dict]) -> list[dict]:
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
            "Match request items to invoice items in one-to-one pairs.\n"
            "Rules:\n"
            "- match by semantic name similarity and unit/quantity consistency.\n"
            "- each request item can be used once.\n"
            "- each invoice item can be used once.\n"
            "- return only confident pairs.\n"
            "Return ONLY JSON array like:\n"
            '[{"request_item_id":"...","invoice_item_id":"..."}]\n'
            f"Request items: {json.dumps(request_items, ensure_ascii=False)}\n"
            f"Invoice items: {json.dumps(invoice_items, ensure_ascii=False)}"
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
