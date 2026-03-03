import uuid

from sqlalchemy.orm import Session

from app.models.invoice import InvoiceItem
from app.models.item_mapping import ItemMapping
from app.models.supply_request import RequestItem


class ItemMappingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_mapping_by_id(self, mapping_id: str) -> ItemMapping | None:
        return self.db.query(ItemMapping).filter(ItemMapping.id == mapping_id).first()

    def get_request_item_by_id(self, request_item_id: str) -> RequestItem | None:
        return self.db.query(RequestItem).filter(RequestItem.id == request_item_id).first()

    def get_invoice_item_by_id(self, invoice_item_id: str) -> InvoiceItem | None:
        return self.db.query(InvoiceItem).filter(InvoiceItem.id == invoice_item_id).first()

    def list_mappings(
        self,
        request_id: int | None = None,
        invoice_id: int | None = None,
        request_item_id: str | None = None,
        invoice_item_id: str | None = None,
    ):
        query = (
            self.db.query(ItemMapping, RequestItem, InvoiceItem)
            .join(RequestItem, RequestItem.id == ItemMapping.request_item_id)
            .join(InvoiceItem, InvoiceItem.id == ItemMapping.invoice_item_id)
        )
        if request_id is not None:
            query = query.filter(ItemMapping.request_id == request_id)
        if invoice_id is not None:
            query = query.filter(ItemMapping.invoice_id == invoice_id)
        if request_item_id:
            query = query.filter(ItemMapping.request_item_id == request_item_id)
        if invoice_item_id:
            query = query.filter(ItemMapping.invoice_item_id == invoice_item_id)

        return query.order_by(ItemMapping.created_at.desc()).all()

    def get_kit_head_quantity(self, request_id: int | None, invoice_id: int | None, group_number: int) -> float | None:
        query = self.db.query(ItemMapping).filter(
            ItemMapping.group_number == group_number,
            ItemMapping.match_type == "kit_head",
        )
        if request_id is None:
            query = query.filter(ItemMapping.request_id.is_(None))
        else:
            query = query.filter(ItemMapping.request_id == request_id)
        if invoice_id is None:
            query = query.filter(ItemMapping.invoice_id.is_(None))
        else:
            query = query.filter(ItemMapping.invoice_id == invoice_id)

        row = query.first()
        return row.mapped_quantity if row else None

    def create_mapping(self, payload: dict) -> ItemMapping:
        row = ItemMapping(id=str(uuid.uuid4()), **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_mapping(self, row: ItemMapping) -> ItemMapping:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_mapping(self, row: ItemMapping) -> None:
        self.db.delete(row)
        self.db.commit()
