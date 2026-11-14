from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status

from app.database import DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.extract_item import (
    ExtractItemSetObjectRequest,
    ExtractItemUpdate,
    FetchSberbankStatementRequest,
    FetchTbankStatementRequest,
)
from app.repositories.business_card_repository import BusinessCardRepository
from app.repositories.contract_extract_repository import ContractExtractRepository
from app.repositories.contract_repository import ContractRepository
from app.repositories.counterparty_repository import CounterpartyRepository
from app.repositories.extract_business_card_repository import ExtractBusinessCardRepository
from app.repositories.extract_item_repository import ExtractItemRepository
from app.repositories.extract_statement_job_repository import ExtractStatementJobRepository
from app.repositories.invoice_payment_extract_repository import InvoicePaymentExtractRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.repositories.settings_api_bank_repository import SettingsApiBankRepository
from app.services.extract_item_service import ExtractItemService
from app.services.extract_statement_job_service import ExtractStatementJobService

extract_items_router = APIRouter(prefix="/extract-items", tags=["ExtractItems"])


def build_service(supply_db: DbSupplySession, reference_db: DbReferenceSession | None = None) -> ExtractItemService:
    return ExtractItemService(
        ExtractItemRepository(supply_db),
        SettingsApiBankRepository(supply_db),
        CounterpartyRepository(reference_db) if reference_db else None,
        ContractExtractRepository(supply_db),
        ContractRepository(supply_db),
        ExtractBusinessCardRepository(supply_db),
        BusinessCardRepository(supply_db),
        ReferenceObjectRepository(reference_db) if reference_db else None,
        InvoicePaymentExtractRepository(supply_db),
    )


def build_job_service(supply_db: DbSupplySession) -> ExtractStatementJobService:
    return ExtractStatementJobService(
        ExtractStatementJobRepository(supply_db),
        SettingsApiBankRepository(supply_db),
    )


@extract_items_router.post(
    "/fetch-sberbank-statement",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Запустить фоновую задачу: получить выписку Сбербанка за день/период и загрузить платежи в extract_items",
    description=(
        "Передайте либо `statement_date` (один день), либо `statement_date_from`+`statement_date_to` "
        "(включительный период — например с 2020-01-01 по сегодня). Запрос сразу возвращает 202 и "
        "объект задачи (`status: pending`) — сама обработка идёт в фоновом потоке, полностью "
        "независимо от этого HTTP-запроса: можно закрыть страницу/вкладку, задача всё равно "
        "доработает до конца. Прогресс и результат смотрите через "
        "`GET /fetch-sberbank-statement/{id}`. Ошибка за один день (нет данных, временный сбой) не "
        "прерывает весь период — такие дни попадают в `errors`, остальные дни обрабатываются дальше. "
        "Можно запускать несколько задач параллельно (для разных счетов/периодов) — они не блокируют "
        "друг друга. Дубликаты строк (по дате операции, сумме, направлению, назначению платежа, "
        "ИНН плательщика/получателя и счёту получателя) не создаются повторно."
    ),
)
def fetch_sberbank_statement(
    payload: FetchSberbankStatementRequest,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_job_service(supply_db).create_job(payload, _session.user_id)


@extract_items_router.get(
    "/fetch-sberbank-statement",
    status_code=status.HTTP_200_OK,
    summary="Список фоновых задач получения выписки",
)
def get_fetch_sberbank_statement_jobs(
    supply_db: DbSupplySession,
    settings_api_bank_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _session=Depends(get_session),
):
    return build_job_service(supply_db).get_jobs(settings_api_bank_id, limit, offset)


@extract_items_router.get(
    "/fetch-sberbank-statement/{job_id}",
    status_code=status.HTTP_200_OK,
    summary="Статус/прогресс фоновой задачи получения выписки",
)
def get_fetch_sberbank_statement_job(
    job_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_job_service(supply_db).get_job(job_id)


@extract_items_router.post(
    "/upload-excel",
    status_code=status.HTTP_200_OK,
    summary="Загрузить выписку из Excel-файла",
    description=(
        "Multipart-форма: `file` (.xlsx), `bank_type` (сейчас реализован только `alfabank`; "
        "`sberbank`/`tbank` вернут 501 — пришлите пример файла, чтобы добавить парсер), "
        "`account_number` — опционально: если не передать, берётся номер счёта, найденный в "
        "самом файле (не для всех банков он там есть). Дедуп такой же, как для Сбербанк-API: "
        "повторная загрузка того же файла не создаёт дублей строк."
    ),
)
async def upload_excel_statement(
    file: Annotated[UploadFile, File(...)],
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    bank_type: Literal["sberbank", "alfabank", "tbank"] = Form(...),
    account_number: str | None = Form(default=None),
    _session=Depends(get_session),
):
    file_bytes = await file.read()
    return build_service(supply_db, reference_db).upload_excel_statement(bank_type, account_number, file_bytes)


@extract_items_router.post(
    "/fetch-tbank-statement",
    status_code=status.HTTP_200_OK,
    summary="Получить выписку Т-Банка по счёту за период и загрузить платежи в extract_items",
    description=(
        "Синхронный вызов (как fetch-sberbank-statement до перевода в фоновую задачу — Т-Банк "
        "сам принимает период одним запросом `from`/`to`, дня за днём дёргать не нужно). "
        "`date_from`/`date_to` — ISO-8601 (`to` опционален). Использует `settings_api_bank_id` "
        "интеграции с `bank_type=tbank` (api_token, без сертификата). Дедуп — как и для "
        "остальных источников (по дате операции, сумме, направлению, назначению платежа, ИНН "
        "плательщика/получателя, счёту получателя и номеру счёта). Маппинг полей проверен на "
        "реальном ответе /v1/statement (payer/receiver, operationAmount, typeOfOperation)."
    ),
)
def fetch_tbank_statement_route(
    payload: FetchTbankStatementRequest,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, reference_db).fetch_and_store_tbank_statement(payload, _session.user_id)


@extract_items_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Список строк выписки",
)
def get_extract_items(
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    payee_id_missing: bool | None = Query(default=None),
    payer_id_missing: bool | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    account_number: str | None = Query(default=None),
    bank_type: str | None = Query(default=None),
    object_id: str | None = Query(default=None, description="Только строки, привязанные к этому объекту"),
    object_missing: bool | None = Query(default=None, description="true — без объекта, false — с объектом"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _session=Depends(get_session),
):
    return build_service(supply_db, reference_db).get_list(
        payee_id_missing, payer_id_missing, date_from, date_to, account_number, bank_type, limit, offset,
        object_id, object_missing,
    )


# literal paths must be registered before the /{item_id} wildcards
@extract_items_router.get(
    "/by-object/{object_id}",
    status_code=status.HTTP_200_OK,
    summary="Платежи (строки выписки), привязанные к объекту, кроме операций по бизнес-картам",
    description=(
        "Строки extract_items с проставленным object_id (PATCH /extract-items/{id} или "
        "POST /extract-items/set-object). По умолчанию операции по бизнес-картам исключены — они "
        "в /extract-business-cards/by-object/{object_id}; exclude_business_cards=false вернёт все. "
        "Ответ: short_name объекта, сводка (total_debit/total_credit/net_spent с учётом возвратов, "
        "сколько операций привязано к платежам по счетам и к договорам) и сами операции с "
        "contract / invoice_payments. Без date_from/date_to — за всё время."
    ),
)
def get_extract_items_by_object(
    object_id: str,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    exclude_business_cards: bool = Query(default=True),
    _session=Depends(get_session),
):
    return build_service(supply_db, reference_db).get_by_object(object_id, date_from, date_to, exclude_business_cards)


@extract_items_router.post(
    "/set-object",
    status_code=status.HTTP_200_OK,
    summary="Привязать несколько строк выписки к объекту (object_id=null — снять привязку)",
)
def set_extract_items_object(
    payload: ExtractItemSetObjectRequest,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, reference_db).set_object(payload)


@extract_items_router.get(
    "/{item_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить строку выписки по ID",
)
def get_extract_item(
    item_id: str,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, reference_db).get_by_id(item_id)


@extract_items_router.patch(
    "/{item_id}",
    status_code=status.HTTP_200_OK,
    summary="Вручную указать payee_id/payer_id/object_id для строки выписки",
)
def update_extract_item(
    item_id: str,
    payload: ExtractItemUpdate,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, reference_db).update(item_id, payload)
