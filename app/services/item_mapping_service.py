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
        return [self._to_response(mapping, request_item, invoice_item) for mapping, request_item, invoice_item in rows]

    def get_by_id(self, mapping_id: str):
        mapping = self.repo.get_mapping_by_id(mapping_id)
        if not mapping:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item mapping not found")

        request_item = self.repo.get_request_item_by_id(mapping.request_item_id)
        invoice_item = self.repo.get_invoice_item_by_id(mapping.invoice_item_id)
        return self._to_response(mapping, request_item, invoice_item)

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

        created = self.repo.create_mapping(data)
        return self._to_response(created, request_item, invoice_item)

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

        for key, value in data.items():
            setattr(mapping, key, value)

        updated = self.repo.save_mapping(mapping)
        return self._to_response(updated, request_item, invoice_item)

    def delete(self, mapping_id: str):
        mapping = self.repo.get_mapping_by_id(mapping_id)
        if not mapping:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item mapping not found")
        self.repo.delete_mapping(mapping)
        return None

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

    def _to_response(self, mapping, request_item, invoice_item):
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
