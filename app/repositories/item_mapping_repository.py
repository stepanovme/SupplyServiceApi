import uuid

from sqlalchemy.orm import Session

from app.models.invoice import InvoiceItem
from app.models.item_mapping import ItemMapping
from app.models.supply_request import RequestItem, UnitRef


class ItemMappingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_mapping_by_id(self, mapping_id: str) -> ItemMapping | None:
        return self.db.query(ItemMapping).filter(ItemMapping.id == mapping_id).first()

    def get_request_item_by_id(self, request_item_id: str) -> RequestItem | None:
        return self.db.query(RequestItem).filter(RequestItem.id == request_item_id).first()

    def get_invoice_item_by_id(self, invoice_item_id: str) -> InvoiceItem | None:
        return self.db.query(InvoiceItem).filter(InvoiceItem.id == invoice_item_id).first()

    def get_request_items_for_matching(self, request_id: int):
        return (
            self.db.query(RequestItem, UnitRef)
            .outerjoin(UnitRef, UnitRef.id == RequestItem.unit_id)
            .filter(RequestItem.request_id == request_id)
            .order_by(RequestItem.num.asc(), RequestItem.id.asc())
            .all()
        )

    def get_invoice_items_for_matching(self, invoice_id: int) -> list[InvoiceItem]:
        return (
            self.db.query(InvoiceItem)
            .filter(InvoiceItem.invoice_id == invoice_id)
            .order_by(InvoiceItem.id.asc())
            .all()
        )

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

    def create_mapping_no_commit(self, payload: dict) -> ItemMapping:
        row = ItemMapping(id=str(uuid.uuid4()), **payload)
        self.db.add(row)
        return row

    def save_mapping(self, row: ItemMapping) -> ItemMapping:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_mapping(self, row: ItemMapping) -> None:
        self.db.delete(row)
        self.db.commit()

    def delete_by_request_invoice(self, request_id: int, invoice_id: int) -> None:
        (
            self.db.query(ItemMapping)
            .filter(
                ItemMapping.request_id == request_id,
                ItemMapping.invoice_id == invoice_id,
            )
            .delete(synchronize_session=False)
        )
        self.db.commit()

    def commit(self) -> None:
        self.db.commit()

    def get_unit_names(self, unit_ids: list[str]) -> dict[str, str]:
        if not unit_ids:
            return {}
        rows = self.db.query(UnitRef.id, UnitRef.name).filter(UnitRef.id.in_(unit_ids)).all()
        return {str(unit_id): unit_name for unit_id, unit_name in rows}
