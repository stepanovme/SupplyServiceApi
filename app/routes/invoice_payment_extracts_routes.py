from fastapi import APIRouter, Depends, Query, status

from app.database import DbAuthSession, DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.invoice_payment_extract import (
    InvoicePaymentExtractBulkCreate,
    InvoicePaymentExtractCreate,
    InvoicePaymentExtractMatchAllRequest,
    InvoicePaymentExtractUpdate,
)
from app.repositories.extract_item_repository import ExtractItemRepository
from app.repositories.invoice_payment_extract_repository import InvoicePaymentExtractRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.routes.invoices_routes import build_invoice_service
from app.services.invoice_payment_extract_service import InvoicePaymentExtractService

invoice_payment_extracts_router = APIRouter(prefix="/invoice-payment-extracts", tags=["InvoicePaymentExtracts"])


def build_service(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession | None = None,
    reference_db: DbReferenceSession | None = None,
) -> InvoicePaymentExtractService:
    # All repositories share ONE session on purpose: applying a match changes invoice_payment
    # rows and inserts the link, and that must commit as a single transaction.
    notifier = build_invoice_service(supply_db, auth_db, reference_db) if auth_db and reference_db else None
    return InvoicePaymentExtractService(
        InvoicePaymentExtractRepository(supply_db),
        InvoiceRepository(supply_db),
        ExtractItemRepository(supply_db),
        notifier,
    )


@invoice_payment_extracts_router.post(
    "/match/{extract_id}",
    status_code=status.HTTP_200_OK,
    summary="Сопоставить строку выписки с оплатой счёта и провести платёж",
    description=(
        "Из назначения платежа берётся «счёт №N от дата». Счёт ищется в invoice по номеру, дате, "
        "provider_id (= payee_id строки) и payer_id (= payer_id строки). Дальше по платежам счёта:\n"
        "• есть запланированный на ту же сумму → он отмечается оплаченным;\n"
        "• запланированный БОЛЬШЕ суммы платежа → он становится оплаченным на сумму платежа, а "
        "остаток создаётся новым запланированным платежом;\n"
        "• запланированные только МЕНЬШЕ суммы платежа → самый крупный из них увеличивается до "
        "суммы платежа и отмечается оплаченным;\n"
        "• запланированных нет → создаётся новый оплаченный платёж.\n"
        "• платёж уже внесён вручную как оплаченный (ни с чем не связан) → строка просто "
        "привязывается к нему, суммы не меняются.\n"
        "Номер и дату счёта сначала ищет регулярка, а если не нашла (например, дата словами «от 14 июля "
        "2023 г») — ИИ (`use_ai=false` отключает); ответ ИИ принимается, только если номер и дата "
        "дословно есть в тексте. Уведомления участникам счёта уходят так же, как при ручной оплате, "
        "кроме случая «платёж уже был оплачен вручную». Обрабатываются только DEBIT-строки. Если "
        "в тексте несколько счетов, не определены payer_id/payee_id, счёт не найден или найдено "
        "несколько, либо оплата превысила бы сумму счёта — ничего не меняется, в ответе `reason`. "
        "`dry_run=true` показывает, что будет сделано, ничего не записывая."
    ),
)
def match_extract_item(
    extract_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    dry_run: bool = Query(default=False),
    use_ai: bool = Query(default=True),
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).match_extract_item(
        extract_id, _session.user_id, dry_run, use_ai
    )


@invoice_payment_extracts_router.post(
    "/match-all",
    status_code=status.HTTP_200_OK,
    summary="Пакетно сопоставить выбранные или ещё не привязанные строки выписки с оплатами счетов",
    description=(
        "Либо `extract_ids: [...]` — обработать ровно эти строки, либо `date_from`/`date_to`/`limit` — "
        "взять до `limit` ещё не привязанных DEBIT-строк, где в назначении платежа упоминается счёт. "
        "`dry_run: true` — только показать, что будет сделано. Строки, которые не удалось "
        "сопоставить, не помечаются как «проверенные» и при повторном вызове обрабатываются заново."
    ),
)
def match_all(
    payload: InvoicePaymentExtractMatchAllRequest,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).match_all(payload, _session.user_id)


@invoice_payment_extracts_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Список связей выписка — платёж по счёту",
)
def get_invoice_payment_extracts(
    supply_db: DbSupplySession,
    extract_id: str | None = Query(default=None),
    invoice_id: int | None = Query(default=None),
    invoice_payment_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _session=Depends(get_session),
):
    return build_service(supply_db).get_list(extract_id, invoice_id, invoice_payment_id, limit, offset)


@invoice_payment_extracts_router.get(
    "/{item_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить связь по ID",
)
def get_invoice_payment_extract(
    item_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).get_by_id(item_id)


@invoice_payment_extracts_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Вручную связать строку выписки с существующим платежом по счёту",
    description=(
        "Только создаёт связь (scenario=manual); сам платёж не изменяется. Одну строку выписки можно "
        "привязать к нескольким платежам (в т.ч. разных счетов): amount — доля строки в этом платеже, "
        "не указан — берётся нераспределённый остаток. Сумма всех привязок строки не может превышать её сумму."
    ),
)
def create_invoice_payment_extract(
    payload: InvoicePaymentExtractCreate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).create_manual(payload, _session.user_id)


@invoice_payment_extracts_router.post(
    "/bulk",
    status_code=status.HTTP_201_CREATED,
    summary="Привязать одну строку выписки сразу к нескольким платежам по счетам",
    description="Атомарно: создаются все связи или ни одной. Сумма amount по всем links не может превышать сумму строки (с учётом уже существующих привязок).",
)
def create_invoice_payment_extracts_bulk(
    payload: InvoicePaymentExtractBulkCreate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).create_bulk(payload, _session.user_id)


@invoice_payment_extracts_router.patch(
    "/{item_id}",
    status_code=status.HTTP_200_OK,
    summary="Изменить долю строки выписки в платеже (amount)",
)
def update_invoice_payment_extract(
    item_id: str,
    payload: InvoicePaymentExtractUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).update_amount(item_id, payload)


@invoice_payment_extracts_router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить связь (платёж остаётся как есть)",
)
def delete_invoice_payment_extract(
    item_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete(item_id)
    return None
