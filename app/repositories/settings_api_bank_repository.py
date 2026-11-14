from sqlalchemy.orm import Session

from app.models.settings_api_bank import SettingsApiBank, SettingsApiBankAccount


class SettingsApiBankRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, item_id: str) -> SettingsApiBank | None:
        return self.db.query(SettingsApiBank).filter(SettingsApiBank.id == item_id).first()

    def get_all(self, bank_type: str | None = None, is_active: bool | None = None) -> list[SettingsApiBank]:
        q = self.db.query(SettingsApiBank)
        if bank_type is not None:
            q = q.filter(SettingsApiBank.bank_type == bank_type)
        if is_active is not None:
            q = q.filter(SettingsApiBank.is_active == is_active)
        return q.order_by(SettingsApiBank.created_at.desc()).all()

    def create(self, row: SettingsApiBank) -> SettingsApiBank:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: SettingsApiBank) -> SettingsApiBank:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, row: SettingsApiBank) -> None:
        self.db.delete(row)
        self.db.commit()

    # --- SettingsApiBankAccount ---

    def get_account_by_id(self, account_id: str) -> SettingsApiBankAccount | None:
        return (
            self.db.query(SettingsApiBankAccount)
            .filter(SettingsApiBankAccount.id == account_id)
            .first()
        )

    def get_accounts_by_bank_id(
        self, settings_api_bank_id: str, is_active: bool | None = None
    ) -> list[SettingsApiBankAccount]:
        q = self.db.query(SettingsApiBankAccount).filter(
            SettingsApiBankAccount.settings_api_bank_id == settings_api_bank_id
        )
        if is_active is not None:
            q = q.filter(SettingsApiBankAccount.is_active == is_active)
        return q.order_by(SettingsApiBankAccount.created_at.desc()).all()

    def get_account_by_bank_and_number(
        self, settings_api_bank_id: str, account_number: str
    ) -> SettingsApiBankAccount | None:
        return (
            self.db.query(SettingsApiBankAccount)
            .filter(
                SettingsApiBankAccount.settings_api_bank_id == settings_api_bank_id,
                SettingsApiBankAccount.account_number == account_number,
            )
            .first()
        )

    def create_account(self, row: SettingsApiBankAccount) -> SettingsApiBankAccount:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_account(self, row: SettingsApiBankAccount) -> SettingsApiBankAccount:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_account(self, row: SettingsApiBankAccount) -> None:
        self.db.delete(row)
        self.db.commit()
