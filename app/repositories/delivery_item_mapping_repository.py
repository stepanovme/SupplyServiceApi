import uuid
from types import SimpleNamespace

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.models.delivery import DeliveryItem
from app.models.delivery_item_mapping import DeliveryItemMapping


class DeliveryItemMappingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._table_columns_cache: dict[str, set[str]] = {}

    def list_mappings(
        self,
        delivery_id: str | None = None,
        delivery_item_id: str | None = None,
        nomenclature_id: str | None = None,
    ) -> list[DeliveryItemMapping]:
        query = self.db.query(DeliveryItemMapping)
        if delivery_id:
            query = query.filter(DeliveryItemMapping.delivery_id == delivery_id)
        if delivery_item_id:
            query = query.filter(DeliveryItemMapping.delivery_item_id == delivery_item_id)
        if nomenclature_id:
            query = query.filter(DeliveryItemMapping.nomenclature_id == nomenclature_id)
        return query.order_by(DeliveryItemMapping.created_at.desc()).all()

    def get_by_id(self, mapping_id: str) -> DeliveryItemMapping | None:
        return self.db.query(DeliveryItemMapping).filter(DeliveryItemMapping.id == mapping_id).first()

    def create(self, payload: dict) -> DeliveryItemMapping:
        row = DeliveryItemMapping(id=str(uuid.uuid4()), **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def create_no_commit(self, payload: dict) -> DeliveryItemMapping:
        row = DeliveryItemMapping(id=str(uuid.uuid4()), **payload)
        self.db.add(row)
        return row

    def save(self, row: DeliveryItemMapping) -> DeliveryItemMapping:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, row: DeliveryItemMapping) -> None:
        self.db.delete(row)
        self.db.commit()

    def delete_by_delivery(self, delivery_id: str) -> None:
        (
            self.db.query(DeliveryItemMapping)
            .filter(DeliveryItemMapping.delivery_id == delivery_id)
            .delete(synchronize_session=False)
        )
        self.db.commit()

    def commit(self) -> None:
        self.db.commit()

    def get_delivery_item_by_id(self, delivery_item_id: str) -> DeliveryItem | None:
        return self.db.query(DeliveryItem).filter(DeliveryItem.id == delivery_item_id).first()

    def get_delivery_items(self, delivery_id: str) -> list[DeliveryItem]:
        return (
            self.db.query(DeliveryItem)
            .filter(DeliveryItem.delivery_id == delivery_id)
            .order_by(DeliveryItem.created_at.asc(), DeliveryItem.id.asc())
            .all()
        )

    def get_nomenclature(self, nomenclature_ids: list[str]) -> dict[str, SimpleNamespace]:
        unique_ids = list({item for item in nomenclature_ids if item})
        if not unique_ids:
            return {}
        columns = self._get_table_columns("nomenclature")
        select_columns = [column for column in ["id", "name", "unit_id", "article"] if column in columns]
        if "id" not in select_columns:
            return {}
        rows = self.db.execute(
            text(
                "SELECT "
                + ", ".join(select_columns)
                + " FROM nomenclature WHERE id IN :ids"
            ).bindparams(bindparam("ids", expanding=True)),
            {"ids": unique_ids},
        ).mappings().all()
        return {
            str(row["id"]): SimpleNamespace(
                id=row["id"],
                name=row.get("name"),
                unit_id=row.get("unit_id"),
                article=row.get("article"),
            )
            for row in rows
        }

    def get_all_nomenclature(self) -> list[SimpleNamespace]:
        columns = self._get_table_columns("nomenclature")
        select_columns = [column for column in ["id", "name", "unit_id", "article"] if column in columns]
        if "id" not in select_columns:
            return []
        rows = self.db.execute(
            text(
                "SELECT "
                + ", ".join(select_columns)
                + " FROM nomenclature ORDER BY name ASC"
            )
        ).mappings().all()
        return [
            SimpleNamespace(
                id=row["id"],
                name=row.get("name"),
                unit_id=row.get("unit_id"),
                article=row.get("article"),
            )
            for row in rows
        ]

    def _get_table_columns(self, table_name: str) -> set[str]:
        cached = self._table_columns_cache.get(table_name)
        if cached is not None:
            return cached
        rows = self.db.execute(text(f"SHOW COLUMNS FROM `{table_name}`")).mappings().all()
        columns = {row["Field"] for row in rows}
        self._table_columns_cache[table_name] = columns
        return columns
