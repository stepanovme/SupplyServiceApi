from sqlalchemy import text
from sqlalchemy.orm import Session


class CounterpartyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._table_columns_cache: dict[str, set[str]] = {}

    def get_counterparty_brief(self, counterparty_id: str | None) -> dict | None:
        if not counterparty_id:
            return None

        counterparty_columns = self._get_table_columns("counterparties")
        if "id" not in counterparty_columns:
            return None

        select_columns = ["id"]
        if "short_name" in counterparty_columns:
            select_columns.append("short_name")
        if "type" in counterparty_columns:
            select_columns.append("type")

        counterparty = self.db.execute(
            text(
                f"SELECT {', '.join(select_columns)} "
                "FROM counterparties "
                "WHERE id = :counterparty_id "
                "LIMIT 1"
            ),
            {"counterparty_id": counterparty_id},
        ).mappings().first()
        if not counterparty:
            return None

        inn: str | None = None
        kpp: str | None = None
        counterparty_type = str(counterparty.get("type") or "").upper()
        if counterparty_type == "IP":
            details = self._get_details_row(
                table_name="details_ip",
                counterparty_id=counterparty_id,
                select_columns=["inn"],
            )
            inn = details.get("inn") if details else None
        elif counterparty_type == "LLC":
            details = self._get_details_row(
                table_name="details_llc",
                counterparty_id=counterparty_id,
                select_columns=["inn", "kpp"],
            )
            if details:
                inn = details.get("inn")
                kpp = details.get("kpp")

        bank = self._get_bank_account_row(counterparty_id)

        return {
            "id": counterparty.get("id"),
            "short_name": counterparty.get("short_name"),
            "inn": inn,
            "kpp": kpp,
            "checking_account": bank.get("checking_account") if bank else None,
        }

    def get_counterparty_names(self, counterparty_ids: list[str]) -> dict[str, str]:
        unique_ids = list({counterparty_id for counterparty_id in counterparty_ids if counterparty_id})
        if not unique_ids:
            return {}

        result: dict[str, str] = {}
        for counterparty_id in unique_ids:
            row = self.get_counterparty_brief(counterparty_id)
            if not row:
                continue
            result[str(counterparty_id)] = row.get("short_name") or ""
        return result

    def find_by_inn(self, inn: str) -> dict | None:
        if not inn:
            return None

        for table_name in ("details_ip", "details_llc"):
            table_columns = self._get_table_columns(table_name)
            if "inn" not in table_columns:
                continue

            fk_column = self._resolve_counterparty_fk_column(table_columns)
            if not fk_column:
                continue

            row = self.db.execute(
                text(
                    f"SELECT {fk_column} AS counterparty_id "
                    f"FROM {table_name} "
                    "WHERE inn = :inn "
                    "LIMIT 1"
                ),
                {"inn": inn},
            ).mappings().first()
            if row:
                counterparty_id = str(row["counterparty_id"])
                return self.get_counterparty_brief(counterparty_id)

        return None

    def _get_details_row(
        self,
        table_name: str,
        counterparty_id: str,
        select_columns: list[str],
    ) -> dict | None:
        table_columns = self._get_table_columns(table_name)
        if not table_columns:
            return None

        fk_column = self._resolve_counterparty_fk_column(table_columns)
        if not fk_column:
            return None

        columns = [column for column in select_columns if column in table_columns]
        if not columns:
            return None

        return self.db.execute(
            text(
                f"SELECT {', '.join(columns)} "
                f"FROM {table_name} "
                f"WHERE {fk_column} = :counterparty_id "
                "LIMIT 1"
            ),
            {"counterparty_id": counterparty_id},
        ).mappings().first()

    def _get_bank_account_row(self, counterparty_id: str) -> dict | None:
        table_columns = self._get_table_columns("bank_accounts")
        if not table_columns:
            return None

        fk_column = self._resolve_counterparty_fk_column(table_columns)
        if not fk_column:
            return None

        account_column = self._resolve_first_existing(
            table_columns,
            ["account_number", "checking_account", "account", "number"],
        )
        if not account_column:
            return None

        where_parts = [f"{fk_column} = :counterparty_id"]
        if "is_main" in table_columns:
            where_parts.append("is_main = 1")
        elif "main" in table_columns:
            where_parts.append("main = 1")

        return self.db.execute(
            text(
                f"SELECT {account_column} AS checking_account "
                "FROM bank_accounts "
                f"WHERE {' AND '.join(where_parts)} "
                "LIMIT 1"
            ),
            {"counterparty_id": counterparty_id},
        ).mappings().first()

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

    @staticmethod
    def _resolve_first_existing(columns: set[str], candidates: list[str]) -> str | None:
        for candidate in candidates:
            if candidate in columns:
                return candidate
        return None

    def _resolve_counterparty_fk_column(self, columns: set[str]) -> str | None:
        direct = self._resolve_first_existing(
            columns,
            [
                "counterparty_id",
                "counterparties_id",
                "counterparty",
                "counterpartyId",
                "counterparty_uuid",
            ],
        )
        if direct:
            return direct

        for column in columns:
            if column != "id" and column.endswith("_id"):
                return column

        return None
