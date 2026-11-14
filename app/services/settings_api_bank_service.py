import os
import uuid

from fastapi import HTTPException, status

from app.models.settings_api_bank import (
    BANK_CONFIG_FIELDS,
    SECRET_CONFIG_FIELDS,
    SettingsApiBank,
    SettingsApiBankAccount,
    SettingsApiBankAccountCreate,
    SettingsApiBankAccountUpdate,
    SettingsApiBankCreate,
    SettingsApiBankUpdate,
)
from app.repositories.settings_api_bank_repository import SettingsApiBankRepository

BASE_BANK_API_FILES_DIR = "/home/webserver/models/bank_api_certs"


class SettingsApiBankService:
    def __init__(self, repo: SettingsApiBankRepository) -> None:
        self.repo = repo

    @staticmethod
    def _mask_secret(value) -> str | None:
        if not value:
            return value
        value = str(value)
        if len(value) <= 4:
            return "*" * len(value)
        return f"{'*' * (len(value) - 4)}{value[-4:]}"

    def _mask_config(self, config: dict) -> dict:
        masked = dict(config or {})
        for key in SECRET_CONFIG_FIELDS:
            if key in masked:
                masked[key] = self._mask_secret(masked[key])
        return masked

    def _serialize(self, row: SettingsApiBank) -> dict:
        return {
            "id": row.id,
            "name": row.name,
            "bank_type": row.bank_type,
            "config": self._mask_config(row.config or {}),
            "is_active": row.is_active,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "created_by": row.created_by,
            "updated_by": row.updated_by,
        }

    @staticmethod
    def _validate_config(bank_type: str, config: dict) -> None:
        fields = BANK_CONFIG_FIELDS.get(bank_type)
        if fields is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported bank_type: {bank_type}")

        unknown = set(config.keys()) - set(fields.keys()) - {"pfx_path", "cert_path", "key_path"}
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown config fields for {bank_type}: {sorted(unknown)}",
            )

        missing = [name for name, required in fields.items() if required and not config.get(name)]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required config fields for {bank_type}: {missing}",
            )

    def get_by_id(self, item_id: str) -> dict:
        row = self.repo.get_by_id(item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank API setting not found")
        return self._serialize(row)

    def get_all(self, bank_type: str | None = None, is_active: bool | None = None) -> list[dict]:
        rows = self.repo.get_all(bank_type, is_active)
        return [self._serialize(row) for row in rows]

    def create(self, payload: SettingsApiBankCreate, created_by: str) -> dict:
        self._validate_config(payload.bank_type, payload.config)
        row = SettingsApiBank(
            id=str(uuid.uuid4()),
            name=payload.name,
            bank_type=payload.bank_type,
            config=payload.config,
            is_active=payload.is_active,
            created_by=created_by,
        )
        created = self.repo.create(row)
        return self._serialize(created)

    def update(self, item_id: str, payload: SettingsApiBankUpdate, updated_by: str) -> dict:
        row = self.repo.get_by_id(item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank API setting not found")

        data = payload.model_dump(exclude_unset=True)
        if "config" in data:
            merged_config = dict(row.config or {})
            merged_config.update(data["config"])
            self._validate_config(row.bank_type, merged_config)
            row.config = merged_config
            data.pop("config")

        for key, value in data.items():
            setattr(row, key, value)
        row.updated_by = updated_by

        updated = self.repo.save(row)
        return self._serialize(updated)

    def delete(self, item_id: str) -> None:
        row = self.repo.get_by_id(item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank API setting not found")
        self.repo.delete(row)

    def _require_bank(self, settings_api_bank_id: str) -> SettingsApiBank:
        bank = self.repo.get_by_id(settings_api_bank_id)
        if not bank:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank API setting not found")
        return bank

    @staticmethod
    def _serialize_account(row: SettingsApiBankAccount) -> dict:
        return {
            "id": row.id,
            "settings_api_bank_id": row.settings_api_bank_id,
            "account_number": row.account_number,
            "name": row.name,
            "currency": row.currency,
            "is_active": row.is_active,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "created_by": row.created_by,
            "updated_by": row.updated_by,
        }

    def get_accounts(self, settings_api_bank_id: str, is_active: bool | None = None) -> list[dict]:
        self._require_bank(settings_api_bank_id)
        rows = self.repo.get_accounts_by_bank_id(settings_api_bank_id, is_active)
        return [self._serialize_account(row) for row in rows]

    def create_account(
        self, settings_api_bank_id: str, payload: SettingsApiBankAccountCreate, created_by: str
    ) -> dict:
        self._require_bank(settings_api_bank_id)

        existing = self.repo.get_account_by_bank_and_number(settings_api_bank_id, payload.account_number)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Этот номер счёта уже добавлен для данной интеграции",
            )

        row = SettingsApiBankAccount(
            id=str(uuid.uuid4()),
            settings_api_bank_id=settings_api_bank_id,
            account_number=payload.account_number,
            name=payload.name,
            currency=payload.currency,
            is_active=payload.is_active,
            created_by=created_by,
        )
        created = self.repo.create_account(row)
        return self._serialize_account(created)

    def update_account(
        self, account_id: str, payload: SettingsApiBankAccountUpdate, updated_by: str
    ) -> dict:
        row = self.repo.get_account_by_id(account_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank account not found")

        data = payload.model_dump(exclude_unset=True)
        if "account_number" in data and data["account_number"] != row.account_number:
            duplicate = self.repo.get_account_by_bank_and_number(
                row.settings_api_bank_id, data["account_number"]
            )
            if duplicate:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Этот номер счёта уже добавлен для данной интеграции",
                )

        for key, value in data.items():
            setattr(row, key, value)
        row.updated_by = updated_by

        updated = self.repo.save_account(row)
        return self._serialize_account(updated)

    def delete_account(self, account_id: str) -> None:
        row = self.repo.get_account_by_id(account_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank account not found")
        self.repo.delete_account(row)

    def upload_pfx(self, item_id: str, original_name: str, file_bytes: bytes, updated_by: str) -> dict:
        row = self.repo.get_by_id(item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank API setting not found")
        if row.bank_type != "sberbank":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="pfx upload is only supported for bank_type=sberbank",
            )

        extension = os.path.splitext(original_name)[1].lower() or ".pfx"
        storage_name = f"{uuid.uuid4().hex}{extension}"
        target_dir = os.path.join(BASE_BANK_API_FILES_DIR, item_id)
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, storage_name)

        with open(file_path, "wb") as f:
            f.write(file_bytes)

        config = dict(row.config or {})
        config["pfx_path"] = file_path
        row.config = config
        row.updated_by = updated_by

        updated = self.repo.save(row)
        return self._serialize(updated)

    def upload_tbank_cert(
        self,
        item_id: str,
        cert_original_name: str,
        cert_bytes: bytes,
        key_original_name: str,
        key_bytes: bytes,
        updated_by: str,
    ) -> dict:
        row = self.repo.get_by_id(item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank API setting not found")
        if row.bank_type != "tbank":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Загрузка сертификата поддержана только для bank_type=tbank",
            )

        target_dir = os.path.join(BASE_BANK_API_FILES_DIR, item_id)
        os.makedirs(target_dir, exist_ok=True)

        cert_extension = os.path.splitext(cert_original_name)[1].lower() or ".pem"
        cert_path = os.path.join(target_dir, f"{uuid.uuid4().hex}{cert_extension}")
        with open(cert_path, "wb") as f:
            f.write(cert_bytes)

        key_extension = os.path.splitext(key_original_name)[1].lower() or ".key"
        key_path = os.path.join(target_dir, f"{uuid.uuid4().hex}{key_extension}")
        with open(key_path, "wb") as f:
            f.write(key_bytes)
        os.chmod(key_path, 0o600)

        config = dict(row.config or {})
        config["cert_path"] = cert_path
        config["key_path"] = key_path
        row.config = config
        row.updated_by = updated_by

        updated = self.repo.save(row)
        return self._serialize(updated)
