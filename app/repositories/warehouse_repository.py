import uuid

from sqlalchemy.orm import Session

from app.models.warehouse import Warehouse


class WarehouseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(self) -> list[Warehouse]:
        return self.db.query(Warehouse).order_by(Warehouse.name.asc()).all()

    def get_by_id(self, warehouse_id: str) -> Warehouse | None:
        return self.db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()

    def create(self, payload: dict) -> Warehouse:
        row = Warehouse(id=str(uuid.uuid4()), **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: Warehouse) -> Warehouse:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, row: Warehouse) -> None:
        self.db.delete(row)
        self.db.commit()
