from types import SimpleNamespace

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.models.deal import Deal, DealDelivery, DealProduct, DealService
from app.models.supply_request import NomenclatureRef, StatusRef, UnitRef
from app.models.warehouse import Warehouse


class DealRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._table_columns_cache: dict[str, set[str]] = {}

    def get_all(self) -> list[Deal]:
        return self.db.query(Deal).order_by(Deal.created_at.desc(), Deal.id.desc()).all()

    def get_by_id(self, deal_id: str) -> Deal | None:
        return self.db.query(Deal).filter(Deal.id == deal_id).first()

    def create(self, row: Deal) -> Deal:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: Deal) -> Deal:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, row: Deal) -> None:
        self.db.delete(row)
        self.db.commit()

    def get_deliveries(self, deal_id: str) -> list[DealDelivery]:
        return self.db.query(DealDelivery).filter(DealDelivery.deal_id == deal_id).order_by(DealDelivery.id.asc()).all()

    def get_delivery_by_id(self, deal_id: str, delivery_id: str) -> DealDelivery | None:
        return (
            self.db.query(DealDelivery)
            .filter(DealDelivery.deal_id == deal_id, DealDelivery.id == delivery_id)
            .first()
        )

    def create_delivery(self, row: DealDelivery) -> DealDelivery:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_delivery(self, row: DealDelivery) -> DealDelivery:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_delivery(self, row: DealDelivery) -> None:
        self.db.delete(row)
        self.db.commit()

    def get_products(self, deal_id: str) -> list[DealProduct]:
        return self.db.query(DealProduct).filter(DealProduct.deal_id == deal_id).order_by(DealProduct.id.asc()).all()

    def get_product_by_id(self, deal_id: str, product_id: str) -> DealProduct | None:
        return (
            self.db.query(DealProduct)
            .filter(DealProduct.deal_id == deal_id, DealProduct.id == product_id)
            .first()
        )

    def create_product(self, row: DealProduct) -> DealProduct:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_product(self, row: DealProduct) -> DealProduct:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_product(self, row: DealProduct) -> None:
        self.db.delete(row)
        self.db.commit()

    def get_services(self, deal_id: str) -> list[DealService]:
        return self.db.query(DealService).filter(DealService.deal_id == deal_id).order_by(DealService.id.asc()).all()

    def get_service_by_id(self, deal_id: str, service_id: str) -> DealService | None:
        return (
            self.db.query(DealService)
            .filter(DealService.deal_id == deal_id, DealService.id == service_id)
            .first()
        )

    def create_service(self, row: DealService) -> DealService:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_service(self, row: DealService) -> DealService:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_service(self, row: DealService) -> None:
        self.db.delete(row)
        self.db.commit()

    def get_status_names(self, status_ids: list[str]) -> dict[str, str]:
        unique_ids = list({status_id for status_id in status_ids if status_id})
        if not unique_ids:
            return {}
        rows = self.db.query(StatusRef.id, StatusRef.name).filter(StatusRef.id.in_(unique_ids)).all()
        return {row_id: row_name for row_id, row_name in rows}

    def get_nomenclature(self, nomenclature_ids: list[str]) -> dict[str, object]:
        unique_ids = list({nomenclature_id for nomenclature_id in nomenclature_ids if nomenclature_id})
        if not unique_ids:
            return {}
        columns = self._get_table_columns("nomenclature")
        select_columns = ["id", "name", "unit_id"]
        if "vat_rate" in columns:
            select_columns.append("vat_rate")
        rows = self.db.execute(
            text(
                f"SELECT {', '.join(select_columns)} "
                "FROM nomenclature "
                "WHERE id IN :ids"
            ).bindparams(bindparam("ids", expanding=True)),
            {"ids": unique_ids},
        ).mappings().all()
        return {
            str(row["id"]): SimpleNamespace(
                id=row["id"],
                name=row.get("name"),
                unit_id=row.get("unit_id"),
                vat_rate=row.get("vat_rate"),
            )
            for row in rows
        }

    def get_unit_names(self, unit_ids: list[str]) -> dict[str, str]:
        unique_ids = list({unit_id for unit_id in unit_ids if unit_id})
        if not unique_ids:
            return {}
        rows = self.db.query(UnitRef.id, UnitRef.name).filter(UnitRef.id.in_(unique_ids)).all()
        return {str(unit_id): unit_name for unit_id, unit_name in rows}

    def get_warehouses(self, warehouse_ids: list[str]) -> dict[str, Warehouse]:
        unique_ids = list({warehouse_id for warehouse_id in warehouse_ids if warehouse_id})
        if not unique_ids:
            return {}
        rows = self.db.query(Warehouse).filter(Warehouse.id.in_(unique_ids)).all()
        return {row.id: row for row in rows}

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

    # ─── Chat ID ────────────────────────────────────────────────────────────

    def get_chat_ids_by_deal(self, deal_ids: list[str]) -> dict[str, int]:
        from app.models.chat import Chat
        if not deal_ids:
            return {}
        chats = (
            self.db.query(Chat)
            .filter(Chat.type == "deal", Chat.deal_id.in_(deal_ids))
            .all()
        )
        return {chat.deal_id: chat.id for chat in chats if chat.deal_id}

    def get_chat_id_by_deal(self, deal_id: str) -> int | None:
        from app.models.chat import Chat
        chat = (
            self.db.query(Chat)
            .filter(Chat.type == "deal", Chat.deal_id == deal_id)
            .first()
        )
        return chat.id if chat else None
