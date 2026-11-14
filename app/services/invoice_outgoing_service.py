from fastapi import HTTPException, status

from app.models.invoice_outgoing import (
    InvoiceOutgoingCreate,
    InvoiceOutgoingItemCreate,
    InvoiceOutgoingItemUpdate,
    InvoiceOutgoingNomenclatureCreate,
    InvoiceOutgoingNomenclatureUpdate,
    InvoiceOutgoingUnitCreate,
    InvoiceOutgoingUnitUpdate,
    InvoiceOutgoingUpdate,
)
from app.repositories.counterparty_repository import CounterpartyRepository
from app.repositories.invoice_outgoing_repository import InvoiceOutgoingRepository


class InvoiceOutgoingService:
    def __init__(
        self,
        repo: InvoiceOutgoingRepository,
        counterparty_repo: CounterpartyRepository | None = None,
    ) -> None:
        self.repo = repo
        self.counterparty_repo = counterparty_repo

    def get_outgoings(self):
        outgoings = self.repo.get_outgoings()
        return self._serialize_list(outgoings)

    def get_outgoing(self, outgoing_id: int):
        outgoing = self.repo.get_outgoing_by_id(outgoing_id)
        if not outgoing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice outgoing not found")
        return self._serialize_one(outgoing)

    def create_outgoing(self, payload: InvoiceOutgoingCreate, user_id: str):
        data = payload.model_dump(exclude_unset=True)
        data["created_by"] = user_id
        row = self.repo.create_outgoing(data)
        return self._serialize_one(row)

    def update_outgoing(self, outgoing_id: int, payload: InvoiceOutgoingUpdate):
        row = self.repo.get_outgoing_by_id(outgoing_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice outgoing not found")
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save_outgoing(row)
        return self._serialize_one(updated)

    def delete_outgoing(self, outgoing_id: int):
        row = self.repo.get_outgoing_by_id(outgoing_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice outgoing not found")
        self.repo.delete_outgoing(row)
        return None

    def get_outgoing_items(self, outgoing_id: int):
        if not self.repo.get_outgoing_by_id(outgoing_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice outgoing not found")
        items = self.repo.get_outgoing_items_by_outgoing_id(outgoing_id)
        return self._serialize_items(items)

    def create_outgoing_item(self, outgoing_id: int, payload: InvoiceOutgoingItemCreate, user_id: str):
        if not self.repo.get_outgoing_by_id(outgoing_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice outgoing not found")
        data = payload.model_dump(exclude_unset=True)
        data["created_by"] = user_id
        created = self.repo.create_outgoing_item(outgoing_id, data)
        return self._serialize_items([created])[0]

    def update_outgoing_item(self, outgoing_id: int, item_id: int, payload: InvoiceOutgoingItemUpdate):
        if not self.repo.get_outgoing_by_id(outgoing_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice outgoing not found")
        row = self.repo.get_outgoing_item_by_id(outgoing_id, item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice outgoing item not found")
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save_outgoing_item(row)
        return self._serialize_items([updated])[0]

    def delete_outgoing_item(self, outgoing_id: int, item_id: int):
        if not self.repo.get_outgoing_by_id(outgoing_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice outgoing not found")
        row = self.repo.get_outgoing_item_by_id(outgoing_id, item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice outgoing item not found")
        self.repo.delete_outgoing_item(row)
        return None

    def get_nomenclatures(self):
        return self._serialize_nomenclatures(self.repo.get_nomenclatures())

    def get_nomenclature(self, nomen_id: str):
        row = self.repo.get_nomenclature_by_id(nomen_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nomenclature not found")
        return self._serialize_nomenclatures([row])[0]

    def create_nomenclature(self, payload: InvoiceOutgoingNomenclatureCreate, user_id: str):
        data = payload.model_dump(exclude_unset=True)
        data["created_by"] = user_id
        created = self.repo.create_nomenclature(data)
        return self._serialize_nomenclatures([created])[0]

    def update_nomenclature(self, nomen_id: str, payload: InvoiceOutgoingNomenclatureUpdate):
        row = self.repo.get_nomenclature_by_id(nomen_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nomenclature not found")
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save_nomenclature(row)
        return self._serialize_nomenclatures([updated])[0]

    def delete_nomenclature(self, nomen_id: str):
        row = self.repo.get_nomenclature_by_id(nomen_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nomenclature not found")
        self.repo.delete_nomenclature(row)
        return None

    def get_units(self):
        return self._serialize_units(self.repo.get_units())

    def get_unit(self, unit_id: str):
        row = self.repo.get_unit_by_id(unit_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
        return self._serialize_units([row])[0]

    def create_unit(self, payload: InvoiceOutgoingUnitCreate, user_id: str):
        data = payload.model_dump(exclude_unset=True)
        data["created_by"] = user_id
        created = self.repo.create_unit(data)
        return self._serialize_units([created])[0]

    def update_unit(self, unit_id: str, payload: InvoiceOutgoingUnitUpdate):
        row = self.repo.get_unit_by_id(unit_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save_unit(row)
        return self._serialize_units([updated])[0]

    def delete_unit(self, unit_id: str):
        row = self.repo.get_unit_by_id(unit_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
        self.repo.delete_unit(row)
        return None

    def _serialize_list(self, outgoings):
        outgoing_ids = [o.id for o in outgoings]
        items_by_outgoing = self.repo.get_outgoing_items_by_outgoing_ids(outgoing_ids)
        nomen_ids = set()
        for item_list in items_by_outgoing.values():
            for item in item_list:
                if item.invoice_outgoing_nomenclature_id:
                    nomen_ids.add(item.invoice_outgoing_nomenclature_id)
        nomenclatures = self.repo.get_nomenclatures_by_ids(list(nomen_ids))
        unit_ids = {n.invoice_outgoing_unit_id for n in nomenclatures.values()}
        units = self.repo.get_units_by_ids(list(unit_ids))

        return [
            self._serialize_outgoing(o, items_by_outgoing.get(o.id, []), nomenclatures, units)
            for o in outgoings
        ]

    def _serialize_one(self, outgoing):
        items = self.repo.get_outgoing_items_by_outgoing_id(outgoing.id)
        nomen_ids = [i.invoice_outgoing_nomenclature_id for i in items if i.invoice_outgoing_nomenclature_id]
        nomenclatures = self.repo.get_nomenclatures_by_ids(nomen_ids)
        unit_ids = {n.invoice_outgoing_unit_id for n in nomenclatures.values()}
        units = self.repo.get_units_by_ids(list(unit_ids))
        return self._serialize_outgoing(outgoing, items, nomenclatures, units)

    def _serialize_outgoing(self, outgoing, items, nomenclatures, units):
        provider = self.counterparty_repo.get_counterparty_brief(outgoing.provider_id) if self.counterparty_repo else None
        payer = self.counterparty_repo.get_counterparty_brief(outgoing.payer_id) if self.counterparty_repo else None
        return {
            "id": outgoing.id,
            "provider_id": outgoing.provider_id,
            "payer_id": outgoing.payer_id,
            "provider": provider,
            "payer": payer,
            "num": outgoing.num,
            "date": outgoing.date,
            "sum": outgoing.sum,
            "Ref_Key": outgoing.Ref_Key,
            "created_at": outgoing.created_at,
            "created_by": outgoing.created_by,
            "items": self._serialize_items(items, nomenclatures, units),
        }

    def _serialize_items(self, items, nomenclatures=None, units=None):
        nomenclatures = nomenclatures or {}
        units = units or {}
        return [
            {
                "id": item.id,
                "invoice_outgoing_nomenclature_id": item.invoice_outgoing_nomenclature_id,
                "nomenclature_name": nomenclatures.get(item.invoice_outgoing_nomenclature_id).name
                if nomenclatures.get(item.invoice_outgoing_nomenclature_id) else None,
                "unit_name": units.get(
                    nomenclatures.get(item.invoice_outgoing_nomenclature_id).invoice_outgoing_unit_id
                ).name
                if (
                    nomenclatures.get(item.invoice_outgoing_nomenclature_id)
                    and units.get(nomenclatures[item.invoice_outgoing_nomenclature_id].invoice_outgoing_unit_id)
                ) else None,
                "name": item.name,
                "quantity": item.quantity,
                "price": item.price,
                "sum": item.sum,
                "nds": item.nds,
                "nds_sum": item.nds_sum,
                "created_at": item.created_at,
                "created_by": item.created_by,
            }
            for item in items
        ]

    def _serialize_nomenclatures(self, nomenclatures):
        unit_ids = [n.invoice_outgoing_unit_id for n in nomenclatures if n.invoice_outgoing_unit_id]
        units = self.repo.get_units_by_ids(unit_ids)
        return [
            {
                "id": n.id,
                "ref_key": n.ref_key,
                "name": n.name,
                "invoice_outgoing_unit_id": n.invoice_outgoing_unit_id,
                "unit_name": units.get(n.invoice_outgoing_unit_id).name if units.get(n.invoice_outgoing_unit_id) else None,
                "created_at": n.created_at,
                "created_by": n.created_by,
            }
            for n in nomenclatures
        ]

    @staticmethod
    def _serialize_units(units):
        return [
            {
                "id": u.id,
                "ref_key": u.ref_key,
                "name": u.name,
                "created_at": u.created_at,
                "created_by": u.created_by,
            }
            for u in units
        ]
