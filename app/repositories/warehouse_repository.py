import uuid
from types import SimpleNamespace

from sqlalchemy import bindparam, text
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.supply_request import NomenclatureRef, UnitRef
from app.models.warehouse import Warehouse, WarehouseList


class WarehouseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._table_columns_cache: dict[str, set[str]] = {}

    def get_all(self) -> list[Warehouse]:
        return self.db.query(Warehouse).order_by(Warehouse.name.asc()).all()

    def get_by_id(self, warehouse_id: str) -> Warehouse | None:
        return self.db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()

    def get_list_by_warehouse_id(self, warehouse_id: str) -> list[WarehouseList]:
        return (
            self.db.query(WarehouseList)
            .filter(WarehouseList.warehouse_id == warehouse_id)
            .order_by(WarehouseList.date.asc(), WarehouseList.id.asc())
            .all()
        )

    def get_list_by_nomenclature_ids(self, nomenclature_ids: list[str]) -> list[WarehouseList]:
        if not nomenclature_ids:
            return []
        return (
            self.db.query(WarehouseList)
            .filter(WarehouseList.nomenclature_id.in_(nomenclature_ids))
            .order_by(WarehouseList.date.asc(), WarehouseList.id.asc())
            .all()
        )

    def get_all_list_rows(self, search: str | None = None) -> list[WarehouseList]:
        query = self.db.query(WarehouseList)
        if search:
            query = query.join(NomenclatureRef, NomenclatureRef.id == WarehouseList.nomenclature_id).filter(
                or_(
                    NomenclatureRef.name.ilike(f"%{search}%"),
                    NomenclatureRef.article.ilike(f"%{search}%"),
                )
            )
        return query.order_by(WarehouseList.date.asc(), WarehouseList.id.asc()).all()

    def get_list_row_by_id(self, warehouse_id: str, row_id: str) -> WarehouseList | None:
        return (
            self.db.query(WarehouseList)
            .filter(
                WarehouseList.warehouse_id == warehouse_id,
                WarehouseList.id == row_id,
            )
            .first()
        )

    def get_list_rows_by_ids(self, row_ids: list[str]) -> list[WarehouseList]:
        unique_ids = list({row_id for row_id in row_ids if row_id})
        if not unique_ids:
            return []
        return self.db.query(WarehouseList).filter(WarehouseList.id.in_(unique_ids)).all()

    def get_nomenclature_by_ids(self, nomenclature_ids: list[str]) -> list[object]:
        unique_ids = list({nomenclature_id for nomenclature_id in nomenclature_ids if nomenclature_id})
        if not unique_ids:
            return []
        columns = self._get_table_columns("nomenclature")
        select_columns = [
            "id",
            "name",
            "unit_id",
        ]
        optional_columns = [
            "description",
            "article",
            "warehouse_category_id",
            "length",
            "width",
            "height",
            "weight",
            "vat_rate",
            "price_opt",
            "price_opt2",
            "price_retail",
            "created_at",
            "created_by",
        ]
        select_columns.extend([column for column in optional_columns if column in columns])
        rows = self.db.execute(
            text(
                f"SELECT {', '.join(select_columns)} "
                "FROM nomenclature "
                "WHERE id IN :ids"
            ).bindparams(bindparam("ids", expanding=True)),
            {"ids": unique_ids},
        ).mappings().all()
        return [
            SimpleNamespace(
                id=row.get("id"),
                name=row.get("name"),
                unit_id=row.get("unit_id"),
                description=row.get("description"),
                article=row.get("article"),
                warehouse_category_id=row.get("warehouse_category_id"),
                length=row.get("length"),
                width=row.get("width"),
                height=row.get("height"),
                weight=row.get("weight"),
                vat_rate=row.get("vat_rate"),
                price_opt=row.get("price_opt"),
                price_opt2=row.get("price_opt2"),
                price_retail=row.get("price_retail"),
                created_at=row.get("created_at"),
                created_by=row.get("created_by"),
            )
            for row in rows
        ]

    def get_units_by_ids(self, unit_ids: list[str]) -> list[UnitRef]:
        unique_ids = list({unit_id for unit_id in unit_ids if unit_id})
        if not unique_ids:
            return []
        return self.db.query(UnitRef).filter(UnitRef.id.in_(unique_ids)).all()

    def create(self, payload: dict) -> Warehouse:
        row = Warehouse(id=str(uuid.uuid4()), **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def create_list_row(self, payload: dict) -> WarehouseList:
        row = WarehouseList(id=str(uuid.uuid4()), **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_list_row_by_id_only(self, row_id: str) -> WarehouseList | None:
        return self.db.query(WarehouseList).filter(WarehouseList.id == row_id).first()

    def get_list_rows_by_warehouse_and_nomenclature(
        self, warehouse_id: str, nomenclature_id: str
    ) -> list[WarehouseList]:
        return (
            self.db.query(WarehouseList)
            .filter(
                WarehouseList.warehouse_id == warehouse_id,
                WarehouseList.nomenclature_id == nomenclature_id,
            )
            .order_by(WarehouseList.date.asc(), WarehouseList.id.asc())
            .all()
        )

    def find_list_row_by_details(
        self,
        warehouse_id: str,
        nomenclature_id: str,
        price: float | None,
        vat_rate: int | None,
        object_levels_id: str | None,
        object_id: str | None,
        delivery_id: str | None,
        toll: bool,
        toll_company_id: str | None,
        attribute: str | None,
    ) -> WarehouseList | None:
        q = self.db.query(WarehouseList).filter(
            WarehouseList.warehouse_id == warehouse_id,
            WarehouseList.nomenclature_id == nomenclature_id,
        )
        if price is not None:
            q = q.filter(WarehouseList.price == price)
        else:
            q = q.filter(WarehouseList.price.is_(None))
        if vat_rate is not None:
            q = q.filter(WarehouseList.vat_rate == vat_rate)
        else:
            q = q.filter(WarehouseList.vat_rate.is_(None))
        if object_levels_id is not None:
            q = q.filter(WarehouseList.object_levels_id == object_levels_id)
        else:
            q = q.filter(WarehouseList.object_levels_id.is_(None))
        if object_id is not None:
            q = q.filter(WarehouseList.object_id == object_id)
        else:
            q = q.filter(WarehouseList.object_id.is_(None))
        if delivery_id is not None:
            q = q.filter(WarehouseList.delivery_id == delivery_id)
        else:
            q = q.filter(WarehouseList.delivery_id.is_(None))
        if toll_company_id is not None:
            q = q.filter(WarehouseList.toll_company_id == toll_company_id)
        else:
            q = q.filter(WarehouseList.toll_company_id.is_(None))
        if attribute is not None:
            q = q.filter(WarehouseList.attribute == attribute)
        else:
            q = q.filter(WarehouseList.attribute.is_(None))
        q = q.filter(WarehouseList.toll == (1 if toll else 0))
        return q.first()

    def save(self, row: Warehouse) -> Warehouse:
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_list_row(self, row: WarehouseList) -> WarehouseList:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, row: Warehouse) -> None:
        self.db.delete(row)
        self.db.commit()

    def delete_list_row(self, row: WarehouseList) -> None:
        self.db.delete(row)
        self.db.commit()

    def _get_table_columns(self, table_name: str) -> set[str]:
        if table_name in self._table_columns_cache:
            return self._table_columns_cache[table_name]
        try:
            rows = self.db.execute(text(f"SHOW COLUMNS FROM {table_name}")).mappings().all()
            columns = {str(row["Field"]) for row in rows}
        except Exception:
            columns = set()
        self._table_columns_cache[table_name] = columns
        return columns
