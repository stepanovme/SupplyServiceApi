import uuid

from sqlalchemy.orm import Session

from app.models.supply_request import NomenclatureRef, UnitRef, WarehouseCategoryRef


class CatalogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_units(self) -> list[UnitRef]:
        return self.db.query(UnitRef).order_by(UnitRef.name.asc()).all()

    def get_warehouse_categories(self) -> list[WarehouseCategoryRef]:
        return self.db.query(WarehouseCategoryRef).order_by(WarehouseCategoryRef.name.asc()).all()

    def get_nomenclature(self, search: str | None = None) -> list[NomenclatureRef]:
        query = self.db.query(NomenclatureRef)
        if search:
            query = query.filter(NomenclatureRef.name.ilike(f"%{search}%"))
        return query.order_by(NomenclatureRef.created_at.desc()).all()

    def get_nomenclature_by_id(self, nomenclature_id: str) -> NomenclatureRef | None:
        return self.db.query(NomenclatureRef).filter(NomenclatureRef.id == nomenclature_id).first()

    def create_nomenclature(self, payload: dict) -> NomenclatureRef:
        item = NomenclatureRef(
            id=str(uuid.uuid4()),
            **payload,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def save_nomenclature(self, item: NomenclatureRef) -> NomenclatureRef:
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete_nomenclature(self, item: NomenclatureRef) -> None:
        self.db.delete(item)
        self.db.commit()
