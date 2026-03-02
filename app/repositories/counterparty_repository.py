from sqlalchemy import text
from sqlalchemy.orm import Session


class CounterpartyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._counterparty_columns: set[str] | None = None

    def get_counterparty_brief(self, counterparty_id: str | None) -> dict | None:
        if not counterparty_id:
            return None

        columns = self._get_counterparty_columns()
        if "id" not in columns:
            return None

        select_columns: list[str] = ["id"]
        for column_name in ("short_name", "inn", "kpp"):
            if column_name in columns:
                select_columns.append(column_name)

        account_column = next(
            (
                column_name
                for column_name in ("checking_account", "settlement_account", "payment_account")
                if column_name in columns
            ),
            None,
        )
        if account_column:
            select_columns.append(f"{account_column} AS checking_account")

        query = text(
            f"SELECT {', '.join(select_columns)} "
            "FROM counterparties "
            "WHERE id = :counterparty_id "
            "LIMIT 1"
        )
        row = self.db.execute(query, {"counterparty_id": counterparty_id}).mappings().first()
        if not row:
            return None

        return {
            "id": row.get("id"),
            "short_name": row.get("short_name"),
            "inn": row.get("inn"),
            "kpp": row.get("kpp"),
            "checking_account": row.get("checking_account"),
        }

    def _get_counterparty_columns(self) -> set[str]:
        if self._counterparty_columns is None:
            try:
                rows = self.db.execute(text("SHOW COLUMNS FROM counterparties")).mappings().all()
                self._counterparty_columns = {str(row["Field"]) for row in rows}
            except Exception:
                self._counterparty_columns = set()
        return self._counterparty_columns
