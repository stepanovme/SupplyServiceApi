from sqlalchemy.orm import Session

from app.models.supply_request import NomenclatureGroup, NomenclatureGroupItem


class NomenclatureGroupRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, payload: dict) -> NomenclatureGroup:
        row = NomenclatureGroup(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_all(self) -> list[NomenclatureGroup]:
        return self.db.query(NomenclatureGroup).order_by(NomenclatureGroup.id.desc()).all()

    def get_by_id(self, group_id: int) -> NomenclatureGroup | None:
        return self.db.query(NomenclatureGroup).filter(NomenclatureGroup.id == group_id).first()

    def update(self, group_id: int, payload: dict) -> NomenclatureGroup | None:
        row = self.get_by_id(group_id)
        if row:
            for key, value in payload.items():
                setattr(row, key, value)
            self.db.commit()
            self.db.refresh(row)
        return row

    def delete(self, group_id: int) -> bool:
        row = self.get_by_id(group_id)
        if not row:
            return False
        self.db.delete(row)
        self.db.commit()
        return True

    def create_item(self, payload: dict) -> NomenclatureGroupItem:
        row = NomenclatureGroupItem(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_item_by_id(self, item_id: str) -> NomenclatureGroupItem | None:
        return self.db.query(NomenclatureGroupItem).filter(NomenclatureGroupItem.id == item_id).first()

    def get_items_by_group(self, group_id: int) -> list[NomenclatureGroupItem]:
        return (
            self.db.query(NomenclatureGroupItem)
            .filter(NomenclatureGroupItem.nomenclature_group_id == group_id)
            .order_by(NomenclatureGroupItem.created_at.desc())
            .all()
        )

    def get_nomenclature_ids_by_group(self, group_id: int) -> list[str]:
        rows = (
            self.db.query(NomenclatureGroupItem.nomenclature_id)
            .filter(NomenclatureGroupItem.nomenclature_group_id == group_id)
            .all()
        )
        return [r[0] for r in rows]

    def delete_item(self, item_id: str) -> bool:
        row = self.get_item_by_id(item_id)
        if not row:
            return False
        self.db.delete(row)
        self.db.commit()
        return True
