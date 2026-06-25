from types import SimpleNamespace

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.models.auth_user import AuthUser


class AuthUserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_ids(self, user_ids: list[str]) -> list[AuthUser]:
        if not user_ids:
            return []
        return self.db.query(AuthUser).filter(AuthUser.id.in_(user_ids)).all()

    def get_contact_by_id(self, user_id: str) -> SimpleNamespace | None:
        rows = self.get_contacts_by_ids([user_id])
        return rows[0] if rows else None

    def get_contacts_by_ids(self, user_ids: list[str]) -> list[SimpleNamespace]:
        unique_ids = list({user_id for user_id in user_ids if user_id})
        if not unique_ids:
            return []

        columns = self._get_users_columns()
        select_columns = ["id", "name", "surname", "patronymic"]
        phone_column = next(
            (
                column
                for column in [
                    "phone",
                    "phone_number",
                    "mobile",
                    "mobile_phone",
                    "contact_phone",
                    "telephone",
                    "cell_phone",
                ]
                if column in columns
            ),
            None,
        )
        if phone_column:
            select_columns.append(phone_column)

        rows = self.db.execute(
            text(f"SELECT {', '.join(select_columns)} FROM users WHERE id IN :ids").bindparams(
                bindparam("ids", expanding=True)
            ),
            {"ids": unique_ids},
        ).mappings().all()
        return [
            SimpleNamespace(
                id=row.get("id"),
                name=row.get("name"),
                surname=row.get("surname"),
                patronymic=row.get("patronymic"),
                phone=row.get(phone_column) if phone_column else None,
            )
            for row in rows
        ]

    def _get_users_columns(self) -> set[str]:
        rows = self.db.execute(text("SHOW COLUMNS FROM users")).mappings().all()
        return {row.get("Field") for row in rows if row.get("Field")}
