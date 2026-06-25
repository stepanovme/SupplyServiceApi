import uuid
from types import SimpleNamespace

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.models.delivery import Delivery, DeliveryItem
from app.models.supply_request import StatusRef
from app.models.warehouse import Warehouse


class DeliveryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._table_columns_cache: dict[str, set[str]] = {}
        self._table_types_cache: dict[str, dict[str, str]] = {}

    def get_all(
        self,
        delivery_from: str | None = None,
        delivery_to: str | None = None,
    ) -> list[Delivery]:
        query = self.db.query(Delivery)
        if delivery_from:
            query = query.filter(Delivery.delivery_from == delivery_from)
        if delivery_to:
            query = query.filter(Delivery.delivery_to == delivery_to)
        return query.order_by(Delivery.created_at.desc()).all()

    def get_by_id(self, delivery_id: str) -> Delivery | None:
        return self.db.query(Delivery).filter(Delivery.id == delivery_id).first()

    def get_next_num(self) -> int:
        max_row = self.db.query(Delivery.num).order_by(Delivery.num.desc()).first()
        return (max_row[0] + 1) if max_row and max_row[0] is not None else 1

    def create(self, payload: dict) -> Delivery:
        row = Delivery(id=str(uuid.uuid4()), **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: Delivery) -> Delivery:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, row: Delivery) -> None:
        self.db.delete(row)
        self.db.commit()

    def get_items(self, delivery_id: str) -> list[DeliveryItem]:
        return (
            self.db.query(DeliveryItem)
            .filter(DeliveryItem.delivery_id == delivery_id)
            .order_by(DeliveryItem.created_at.asc(), DeliveryItem.id.asc())
            .all()
        )

    def get_item_by_id(self, delivery_id: str, item_id: str) -> DeliveryItem | None:
        return (
            self.db.query(DeliveryItem)
            .filter(DeliveryItem.delivery_id == delivery_id, DeliveryItem.id == item_id)
            .first()
        )

    def create_item(self, delivery_id: str, payload: dict) -> DeliveryItem:
        payload = self.coerce_item_payload_to_schema(payload)
        row = DeliveryItem(id=str(uuid.uuid4()), delivery_id=delivery_id, **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_item(self, row: DeliveryItem) -> DeliveryItem:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_item(self, row: DeliveryItem) -> None:
        self.db.delete(row)
        self.db.commit()

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

    def get_warehouses(self, warehouse_ids: list[str]) -> dict[str, Warehouse]:
        unique_ids = list({item for item in warehouse_ids if item})
        if not unique_ids:
            return {}
        rows = self.db.query(Warehouse).filter(Warehouse.id.in_(unique_ids)).all()
        return {row.id: row for row in rows}

    def get_status_names(self, status_ids: list[str]) -> dict[str, str]:
        unique_ids = list({item for item in status_ids if item})
        if not unique_ids:
            return {}
        rows = self.db.query(StatusRef.id, StatusRef.name).filter(StatusRef.id.in_(unique_ids)).all()
        return {row_id: row_name for row_id, row_name in rows}

    def _get_table_columns(self, table_name: str) -> set[str]:
        cached = self._table_columns_cache.get(table_name)
        if cached is not None:
            return cached
        rows = self.db.execute(text(f"SHOW COLUMNS FROM `{table_name}`")).mappings().all()
        columns = {row["Field"] for row in rows}
        self._table_types_cache[table_name] = {row["Field"]: str(row["Type"]).lower() for row in rows}
        self._table_columns_cache[table_name] = columns
        return columns

    def coerce_item_payload_to_schema(self, payload: dict) -> dict:
        normalized = dict(payload)
        field_types = self._get_table_field_types("delivery_items")
        for field_name in ("request_item_id", "invoice_item_id"):
            value = normalized.get(field_name)
            if value is None:
                continue
            field_type = field_types.get(field_name, "")
            if "int" in field_type:
                value_str = str(value).strip()
                normalized[field_name] = int(value_str) if value_str.isdigit() else None
        return normalized

    def _get_table_field_types(self, table_name: str) -> dict[str, str]:
        if table_name not in self._table_types_cache:
            self._get_table_columns(table_name)
        return self._table_types_cache.get(table_name, {})
