import uuid
from types import SimpleNamespace

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.models.supply_request import NomenclatureRef, UnitRef
from app.models.upd_document import UpdDocument, UpdDocumentItem
from app.models.upd_item_mapping import UpdItemMapping
from app.models.warehouse import Warehouse


class UpdItemMappingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._table_columns_cache: dict[str, set[str]] = {}

    def get_mapping_by_id(self, mapping_id: str) -> UpdItemMapping | None:
        return self.db.query(UpdItemMapping).filter(UpdItemMapping.id == mapping_id).first()

    def list_mappings(
        self,
        upd_documents_id: str | None = None,
        upd_documents_item_id: str | None = None,
        nomenclature_id: str | None = None,
    ):
        query = (
            self.db.query(UpdItemMapping, UpdDocumentItem)
            .outerjoin(UpdDocumentItem, UpdDocumentItem.id == UpdItemMapping.upd_documents_item_id)
        )
        if upd_documents_id:
            query = query.filter(UpdItemMapping.upd_documents_id == upd_documents_id)
        if upd_documents_item_id:
            query = query.filter(UpdItemMapping.upd_documents_item_id == upd_documents_item_id)
        if nomenclature_id:
            query = query.filter(UpdItemMapping.nomenclature_id == nomenclature_id)
        rows = query.order_by(UpdItemMapping.created_at.desc()).all()
        nomenclature_map = self._get_nomenclature_by_ids(
            [mapping.nomenclature_id for mapping, _ in rows if mapping.nomenclature_id]
        )
        return [(mapping, document_item, nomenclature_map.get(mapping.nomenclature_id)) for mapping, document_item in rows]

    def create_mapping(self, payload: dict) -> UpdItemMapping:
        row = UpdItemMapping(id=str(uuid.uuid4()), **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def create_mapping_no_commit(self, payload: dict) -> UpdItemMapping:
        row = UpdItemMapping(id=str(uuid.uuid4()), **payload)
        self.db.add(row)
        return row

    def save_mapping(self, row: UpdItemMapping) -> UpdItemMapping:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_mapping(self, row: UpdItemMapping) -> None:
        self.db.delete(row)
        self.db.commit()

    def delete_by_document(self, upd_documents_id: str) -> None:
        (
            self.db.query(UpdItemMapping)
            .filter(UpdItemMapping.upd_documents_id == upd_documents_id)
            .delete(synchronize_session=False)
        )
        self.db.commit()

    def commit(self) -> None:
        self.db.commit()

    def get_document_by_id(self, upd_documents_id: str) -> UpdDocument | None:
        return self.db.query(UpdDocument).filter(UpdDocument.id == upd_documents_id).first()

    def get_document_item_by_id(self, item_id: str) -> UpdDocumentItem | None:
        return self.db.query(UpdDocumentItem).filter(UpdDocumentItem.id == item_id).first()

    def get_document_items(self, upd_documents_id: str) -> list[UpdDocumentItem]:
        return (
            self.db.query(UpdDocumentItem)
            .filter(UpdDocumentItem.upd_documents_id == upd_documents_id)
            .order_by(UpdDocumentItem.id.asc())
            .all()
        )

    def get_nomenclature_by_id(self, nomenclature_id: str) -> SimpleNamespace | None:
        return self._get_nomenclature_by_ids([nomenclature_id]).get(nomenclature_id)

    def get_all_nomenclature(self) -> list[SimpleNamespace]:
        available_columns = self._get_table_columns("nomenclature")
        select_columns = self._get_nomenclature_select_columns(available_columns)
        query = text(
            "SELECT "
            + ", ".join(f"`{column}`" for column in select_columns)
            + " FROM `nomenclature` ORDER BY `name` ASC"
        )
        rows = self.db.execute(query).mappings().all()
        return [self._build_nomenclature_namespace(row, select_columns) for row in rows]

    def get_warehouse_names(self, warehouse_ids: list[str]) -> dict[str, str]:
        unique_ids = list({warehouse_id for warehouse_id in warehouse_ids if warehouse_id})
        if not unique_ids:
            return {}
        rows = self.db.query(Warehouse.id, Warehouse.name).filter(Warehouse.id.in_(unique_ids)).all()
        return {str(warehouse_id): warehouse_name for warehouse_id, warehouse_name in rows}

    def get_unit_names(self, unit_ids: list[str]) -> dict[str, str]:
        unique_ids = list({unit_id for unit_id in unit_ids if unit_id})
        if not unique_ids:
            return {}
        rows = self.db.query(UnitRef.id, UnitRef.name).filter(UnitRef.id.in_(unique_ids)).all()
        return {str(unit_id): unit_name for unit_id, unit_name in rows}

    def _get_nomenclature_by_ids(self, nomenclature_ids: list[str]) -> dict[str, SimpleNamespace]:
        unique_ids = list({nomenclature_id for nomenclature_id in nomenclature_ids if nomenclature_id})
        if not unique_ids:
            return {}
        available_columns = self._get_table_columns("nomenclature")
        select_columns = self._get_nomenclature_select_columns(available_columns)
        query = text(
            "SELECT "
            + ", ".join(f"`{column}`" for column in select_columns)
            + " FROM `nomenclature` WHERE `id` IN :ids"
        ).bindparams(bindparam("ids", expanding=True))
        rows = self.db.execute(query, {"ids": unique_ids}).mappings().all()
        return {
            row["id"]: self._build_nomenclature_namespace(row, select_columns)
            for row in rows
        }

    def _get_nomenclature_select_columns(self, available_columns: set[str]) -> list[str]:
        select_columns = [
            "id",
            "warehouse_category_id",
            "name",
            "description",
            "article",
            "unit_id",
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
        return [column for column in select_columns if column in available_columns]

    def _build_nomenclature_namespace(self, row, select_columns: list[str]) -> SimpleNamespace:
        payload = {column: row.get(column) for column in select_columns}
        payload.setdefault("vat_rate", None)
        payload.setdefault("price_opt", None)
        payload.setdefault("price_opt2", None)
        payload.setdefault("price_retail", None)
        return SimpleNamespace(**payload)

    def _get_table_columns(self, table_name: str) -> set[str]:
        cached = self._table_columns_cache.get(table_name)
        if cached is not None:
            return cached
        rows = self.db.execute(text(f"SHOW COLUMNS FROM `{table_name}`")).mappings().all()
        columns = {row["Field"] for row in rows}
        self._table_columns_cache[table_name] = columns
        return columns
