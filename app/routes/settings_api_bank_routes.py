from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.settings_api_bank import (
    SettingsApiBankAccountCreate,
    SettingsApiBankAccountUpdate,
    SettingsApiBankCreate,
    SettingsApiBankUpdate,
)
from app.repositories.settings_api_bank_repository import SettingsApiBankRepository
from app.services.settings_api_bank_service import SettingsApiBankService

settings_api_bank_router = APIRouter(prefix="/settings-api-bank", tags=["SettingsApiBank"])
settings_api_bank_accounts_router = APIRouter(
    prefix="/settings-api-bank-accounts", tags=["SettingsApiBankAccounts"]
)


def build_service(supply_db: DbSupplySession) -> SettingsApiBankService:
    return SettingsApiBankService(SettingsApiBankRepository(supply_db))


@settings_api_bank_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Список настроек подключения к банкам",
)
def get_settings(
    supply_db: DbSupplySession,
    bank_type: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    _session=Depends(get_session),
):
    return build_service(supply_db).get_all(bank_type, is_active)


@settings_api_bank_router.get(
    "/{item_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить настройку подключения к банку по ID",
)
def get_setting(
    item_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).get_by_id(item_id)


@settings_api_bank_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать настройку подключения к банку",
)
def create_setting(
    payload: SettingsApiBankCreate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).create(payload, _session.user_id)


@settings_api_bank_router.patch(
    "/{item_id}",
    status_code=status.HTTP_200_OK,
    summary="Изменить настройку подключения к банку",
)
def update_setting(
    item_id: str,
    payload: SettingsApiBankUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).update(item_id, payload, _session.user_id)


@settings_api_bank_router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить настройку подключения к банку",
)
def delete_setting(
    item_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete(item_id)
    return None


@settings_api_bank_router.post(
    "/{item_id}/pfx",
    status_code=status.HTTP_200_OK,
    summary="Загрузить PFX-сертификат для интеграции (сейчас только sberbank)",
)
async def upload_pfx(
    item_id: str,
    file: Annotated[UploadFile, File(...)],
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    file_bytes = await file.read()
    return build_service(supply_db).upload_pfx(item_id, file.filename or "cert.pfx", file_bytes, _session.user_id)


@settings_api_bank_router.post(
    "/{item_id}/tbank-cert",
    status_code=status.HTTP_200_OK,
    summary="Загрузить клиентский сертификат (mTLS) для интеграции Т-Банка",
    description=(
        "Multipart-форма с двумя файлами: `cert` (PEM-сертификат, например "
        "2-certificate-....pem) и `key` (приватный ключ, например 2-private.key). "
        "Только для интеграций с bank_type=tbank — T-Bank OpenAPI требует клиентский TLS-"
        "сертификат в дополнение к Bearer-токену."
    ),
)
async def upload_tbank_cert(
    item_id: str,
    cert: Annotated[UploadFile, File(...)],
    key: Annotated[UploadFile, File(...)],
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    cert_bytes = await cert.read()
    key_bytes = await key.read()
    return build_service(supply_db).upload_tbank_cert(
        item_id,
        cert.filename or "cert.pem",
        cert_bytes,
        key.filename or "key.pem",
        key_bytes,
        _session.user_id,
    )


# --- SettingsApiBankAccount ---

@settings_api_bank_router.get(
    "/{item_id}/accounts",
    status_code=status.HTTP_200_OK,
    summary="Список счетов, привязанных к интеграции",
)
def get_bank_accounts(
    item_id: str,
    supply_db: DbSupplySession,
    is_active: bool | None = Query(default=None),
    _session=Depends(get_session),
):
    return build_service(supply_db).get_accounts(item_id, is_active)


@settings_api_bank_router.post(
    "/{item_id}/accounts",
    status_code=status.HTTP_201_CREATED,
    summary="Привязать счёт к интеграции",
)
def create_bank_account(
    item_id: str,
    payload: SettingsApiBankAccountCreate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).create_account(item_id, payload, _session.user_id)


@settings_api_bank_accounts_router.patch(
    "/{account_id}",
    status_code=status.HTTP_200_OK,
    summary="Изменить счёт интеграции",
)
def update_bank_account(
    account_id: str,
    payload: SettingsApiBankAccountUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).update_account(account_id, payload, _session.user_id)


@settings_api_bank_accounts_router.delete(
    "/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить счёт интеграции",
)
def delete_bank_account(
    account_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete_account(account_id)
    return None
