from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.invoice_outgoing import (
    InvoiceOutgoing,
    InvoiceOutgoingItem,
    InvoiceOutgoingNomenclature,
    InvoiceOutgoingUnit,
)


class InvoiceOutgoingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_outgoing(self, payload: dict) -> InvoiceOutgoing:
        row = InvoiceOutgoing(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_outgoing_by_id(self, outgoing_id: int) -> InvoiceOutgoing | None:
        return self.db.query(InvoiceOutgoing).filter(InvoiceOutgoing.id == outgoing_id).first()

    def get_outgoings(self) -> list[InvoiceOutgoing]:
        return self.db.query(InvoiceOutgoing).order_by(InvoiceOutgoing.id.desc()).all()

    def get_outgoing_by_ref_key(self, ref_key: str) -> InvoiceOutgoing | None:
        return self.db.query(InvoiceOutgoing).filter(InvoiceOutgoing.Ref_Key == ref_key).first()

    def save_outgoing(self, row: InvoiceOutgoing) -> InvoiceOutgoing:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_outgoing(self, row: InvoiceOutgoing) -> None:
        self.db.delete(row)
        self.db.commit()

    def create_outgoing_item(self, outgoing_id: int, payload: dict) -> InvoiceOutgoingItem:
        max_id = self.db.query(func.max(InvoiceOutgoingItem.id)).scalar() or 0
        row = InvoiceOutgoingItem(id=max_id + 1, invoice_outgoing=outgoing_id, **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_outgoing_item_by_id(self, outgoing_id: int, item_id: int) -> InvoiceOutgoingItem | None:
        return (
            self.db.query(InvoiceOutgoingItem)
            .filter(
                InvoiceOutgoingItem.invoice_outgoing == outgoing_id,
                InvoiceOutgoingItem.id == item_id,
            )
            .first()
        )

    def get_outgoing_items_by_outgoing_id(self, outgoing_id: int) -> list[InvoiceOutgoingItem]:
        return (
            self.db.query(InvoiceOutgoingItem)
            .filter(InvoiceOutgoingItem.invoice_outgoing == outgoing_id)
            .all()
        )

    def get_outgoing_items_by_outgoing_ids(self, outgoing_ids: list[int]) -> dict[int, list[InvoiceOutgoingItem]]:
        if not outgoing_ids:
            return {}
        rows = (
            self.db.query(InvoiceOutgoingItem)
            .filter(InvoiceOutgoingItem.invoice_outgoing.in_(outgoing_ids))
            .all()
        )
        result: dict[int, list[InvoiceOutgoingItem]] = {}
        for row in rows:
            result.setdefault(row.invoice_outgoing, []).append(row)
        return result

    def save_outgoing_item(self, row: InvoiceOutgoingItem) -> InvoiceOutgoingItem:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_outgoing_item(self, row: InvoiceOutgoingItem) -> None:
        self.db.delete(row)
        self.db.commit()

    def get_nomenclature_by_id(self, nomen_id: str) -> InvoiceOutgoingNomenclature | None:
        return self.db.query(InvoiceOutgoingNomenclature).filter(InvoiceOutgoingNomenclature.id == nomen_id).first()

    def get_nomenclatures(self) -> list[InvoiceOutgoingNomenclature]:
        return self.db.query(InvoiceOutgoingNomenclature).order_by(InvoiceOutgoingNomenclature.name).all()

    def get_nomenclatures_by_ids(self, ids: list[str]) -> dict[str, InvoiceOutgoingNomenclature]:
        if not ids:
            return {}
        rows = (
            self.db.query(InvoiceOutgoingNomenclature)
            .filter(InvoiceOutgoingNomenclature.id.in_(ids))
            .all()
        )
        return {row.id: row for row in rows}

    def create_nomenclature(self, payload: dict) -> InvoiceOutgoingNomenclature:
        row = InvoiceOutgoingNomenclature(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_nomenclature(self, row: InvoiceOutgoingNomenclature) -> InvoiceOutgoingNomenclature:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_nomenclature(self, row: InvoiceOutgoingNomenclature) -> None:
        self.db.delete(row)
        self.db.commit()

    def get_unit_by_id(self, unit_id: str) -> InvoiceOutgoingUnit | None:
        return self.db.query(InvoiceOutgoingUnit).filter(InvoiceOutgoingUnit.id == unit_id).first()

    def get_units(self) -> list[InvoiceOutgoingUnit]:
        return self.db.query(InvoiceOutgoingUnit).order_by(InvoiceOutgoingUnit.name).all()

    def get_units_by_ids(self, ids: list[str]) -> dict[str, InvoiceOutgoingUnit]:
        if not ids:
            return {}
        rows = (
            self.db.query(InvoiceOutgoingUnit)
            .filter(InvoiceOutgoingUnit.id.in_(ids))
            .all()
        )
        return {row.id: row for row in rows}

    def create_unit(self, payload: dict) -> InvoiceOutgoingUnit:
        row = InvoiceOutgoingUnit(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_unit(self, row: InvoiceOutgoingUnit) -> InvoiceOutgoingUnit:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_unit(self, row: InvoiceOutgoingUnit) -> None:
        self.db.delete(row)
        self.db.commit()
