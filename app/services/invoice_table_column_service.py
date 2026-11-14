from app.models.invoice_table_column import InvoiceTableColumnBulkUpdate
from app.repositories.invoice_table_column_repository import (
    DEFAULT_COLUMNS,
    InvoiceTableColumnRepository,
)


class InvoiceTableColumnService:
    def __init__(self, repo: InvoiceTableColumnRepository) -> None:
        self.repo = repo

    def get_columns(self, user_id: str) -> list[dict]:
        rows = self.repo.get_by_user(user_id)
        if not rows:
            return [
                {
                    "column_key": col["column_key"],
                    "position": col["position"],
                    "is_visible": True,
                }
                for col in DEFAULT_COLUMNS
            ]
        return [
            {
                "column_key": row.column_key,
                "position": row.position,
                "is_visible": bool(row.is_visible),
            }
            for row in rows
        ]

    def update_columns(self, user_id: str, payload: InvoiceTableColumnBulkUpdate) -> list[dict]:
        columns = [
            {
                "column_key": col.column_key,
                "position": col.position,
                "is_visible": col.is_visible,
            }
            for col in payload.columns
        ]
        self.repo.upsert_all(user_id, columns)
        return self.get_columns(user_id)
