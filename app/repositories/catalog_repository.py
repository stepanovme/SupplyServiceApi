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
