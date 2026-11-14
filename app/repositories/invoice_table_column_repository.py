import uuid

from sqlalchemy.orm import Session

from app.models.invoice_table_column import InvoiceTableColumn


DEFAULT_COLUMNS = [
    {"column_key": "id", "position": 0},
    {"column_key": "num", "position": 1},
    {"column_key": "provider", "position": 2},
    {"column_key": "payer", "position": 3},
    {"column_key": "amount", "position": 4},
    {"column_key": "payment", "position": 5},
    {"column_key": "status", "position": 6},
    {"column_key": "project", "position": 7},
    {"column_key": "participants", "position": 8},
    {"column_key": "comment", "position": 9},
]


class InvoiceTableColumnRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_user(self, user_id: str) -> list[InvoiceTableColumn]:
        return (
            self.db.query(InvoiceTableColumn)
            .filter(InvoiceTableColumn.user_id == user_id)
            .order_by(InvoiceTableColumn.position)
            .all()
        )

    def upsert_all(self, user_id: str, columns: list[dict]) -> list[InvoiceTableColumn]:
        existing = self.db.query(InvoiceTableColumn).filter(InvoiceTableColumn.user_id == user_id).all()
        for row in existing:
            self.db.delete(row)
        self.db.flush()

        created = []
        for col in columns:
            row = InvoiceTableColumn(
                id=str(uuid.uuid4()),
                user_id=user_id,
                column_key=col["column_key"],
                position=col["position"],
                is_visible=1 if col.get("is_visible", True) else 0,
            )
            self.db.add(row)
            created.append(row)

        self.db.commit()
        for row in created:
            self.db.refresh(row)
        return created
