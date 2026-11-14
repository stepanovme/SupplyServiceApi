from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.database import DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.extract import (
    ExtractCreate,
    ExtractItemCreate,
    ExtractItemPaymentCreate,
    ExtractItemPaymentUpdate,
    ExtractItemUpdate,
    ExtractUpdate,
)
from app.models.session import SessionDB
from app.repositories.contract_repository import ContractRepository
from app.repositories.counterparty_repository import CounterpartyRepository
from app.repositories.documents_link_repository import DocumentsLinkRepository
from app.repositories.extract_repository import ExtractRepository
from app.repositories.invoice_outgoing_repository import InvoiceOutgoingRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.services.extract_service import ExtractService

extracts_router = APIRouter(prefix="/extracts", tags=["Extracts"])


def build_service(db: DbSupplySession, reference_db: DbReferenceSession | None = None) -> ExtractService:
    return ExtractService(ExtractRepository(db), reference_db,
                          counterparty_repo=CounterpartyRepository(reference_db) if reference_db else None)


# --- Parse & Create (must be before /{extract_id}) ---

@extracts_router.post(
    "/parse",
    status_code=status.HTTP_201_CREATED,
    summary="Загрузить выписку и распознать через Mistral AI",
)
def parse_extract(
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session: SessionDB = Depends(get_session),
    file: UploadFile = File(...),
):
    return build_service(db, reference_db).parse_and_create(file, str(_session.user_id))


@extracts_router.post(
    "/parse-purpose",
    status_code=status.HTTP_200_OK,
    summary="Распознать одно назначение платежа через Mistral AI",
)
def parse_purpose(
    body: dict,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    purpose = body.get("payment_purpose", "")
    if not purpose:
        raise HTTPException(status_code=400, detail="payment_purpose is required")
    return build_service(db).parse_purpose_with_ai(purpose)


@extracts_router.post(
    "/{extract_id}/parse-items",
    status_code=status.HTTP_200_OK,
    summary="Распознать и найти счета в БД",
)
def parse_extract_items(
    extract_id: int,
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session: SessionDB = Depends(get_session),
):
    service = build_service(db, reference_db)
    items = service.repo.get_items_by_extract_id(extract_id)
    if not items:
        raise HTTPException(status_code=404, detail="Extract items not found")
    return service.parse_items_with_lookup(
        items, str(_session.user_id),
        invoice_repo=InvoiceRepository(db),
        outgoing_repo=InvoiceOutgoingRepository(db),
        contract_repo=ContractRepository(db),
        doc_link_repo=DocumentsLinkRepository(db),
    )


@extracts_router.post(
    "/{extract_id}/match",
    status_code=status.HTTP_200_OK,
    summary="Автоматически сопоставить платежи выписки с документами в системе",
)
def match_extract(
    extract_id: int,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    service = build_service(db)
    return service.match_items(
        extract_id, str(_session.user_id),
        invoice_repo=InvoiceRepository(db),
        outgoing_repo=InvoiceOutgoingRepository(db),
        contract_repo=ContractRepository(db),
        doc_link_repo=DocumentsLinkRepository(db),
    )


# --- Extracts ---

@extracts_router.get("", status_code=status.HTTP_200_OK, summary="Получить список выписок")
def get_extracts(
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    return build_service(db).get_extracts()


@extracts_router.get("/{extract_id}", status_code=status.HTTP_200_OK, summary="Получить выписку по ID")
def get_extract(
    extract_id: int,
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session: SessionDB = Depends(get_session),
):
    return build_service(db, reference_db).get_extract(extract_id)


@extracts_router.post("", status_code=status.HTTP_201_CREATED, summary="Создать выписку")
def create_extract(
    payload: ExtractCreate,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    return build_service(db).create_extract(payload, str(_session.user_id))


@extracts_router.patch("/{extract_id}", status_code=status.HTTP_200_OK, summary="Обновить выписку")
def update_extract(
    extract_id: int,
    payload: ExtractUpdate,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    return build_service(db).update_extract(extract_id, payload, str(_session.user_id))


@extracts_router.delete("/{extract_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить выписку")
def delete_extract(
    extract_id: int,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    build_service(db).delete_extract(extract_id)


# --- Items ---

@extracts_router.get("/{extract_id}/items", status_code=status.HTTP_200_OK, summary="Получить элементы выписки")
def get_items(
    extract_id: int,
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session: SessionDB = Depends(get_session),
):
    return build_service(db, reference_db).get_items(extract_id)


@extracts_router.get("/items/{item_id}", status_code=status.HTTP_200_OK, summary="Получить элемент выписки по ID")
def get_item(
    item_id: str,
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session: SessionDB = Depends(get_session),
):
    return build_service(db).get_item(item_id)


@extracts_router.post("/{extract_id}/items", status_code=status.HTTP_201_CREATED, summary="Создать элемент выписки")
def create_item(
    extract_id: int,
    payload: ExtractItemCreate,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    return build_service(db).create_item(extract_id, payload)


@extracts_router.patch("/items/{item_id}", status_code=status.HTTP_200_OK, summary="Обновить элемент выписки")
def update_item(
    item_id: str,
    payload: ExtractItemUpdate,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    return build_service(db).update_item(item_id, payload)


@extracts_router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить элемент выписки")
def delete_item(
    item_id: str,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    build_service(db).delete_item(item_id)


# --- Files ---

@extracts_router.post("/{extract_id}/files", status_code=status.HTTP_201_CREATED, summary="Загрузить файл выписки")
def upload_file(
    extract_id: int,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
    file: UploadFile = File(...),
):
    return build_service(db).upload_file(extract_id, file, str(_session.user_id))


@extracts_router.get("/{extract_id}/files", status_code=status.HTTP_200_OK, summary="Получить файлы выписки")
def get_files(
    extract_id: int,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    return build_service(db).get_files(extract_id)


@extracts_router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить файл выписки")
def delete_file(
    file_id: str,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    build_service(db).delete_file(file_id)


@extracts_router.get("/files/{file_id}/download", status_code=status.HTTP_200_OK, summary="Скачать файл выписки")
def download_file(
    file_id: str,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    row = build_service(db).get_file(file_id)
    return FileResponse(row.file_path, filename=row.original_name)


# --- Payments ---

@extracts_router.get("/items/{item_id}/payments", status_code=status.HTTP_200_OK, summary="Получить платежи элемента")
def get_payments(
    item_id: str,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    return build_service(db).get_payments(item_id)


@extracts_router.post("/items/{item_id}/payments", status_code=status.HTTP_201_CREATED, summary="Создать платеж элемента")
def create_payment(
    item_id: str,
    payload: ExtractItemPaymentCreate,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    return build_service(db).create_payment(payload, str(_session.user_id))


@extracts_router.patch("/payments/{payment_id}", status_code=status.HTTP_200_OK, summary="Обновить платеж")
def update_payment(
    payment_id: str,
    payload: ExtractItemPaymentUpdate,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    return build_service(db).update_payment(payment_id, payload)


@extracts_router.delete("/payments/{payment_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить платеж")
def delete_payment(
    payment_id: str,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    build_service(db).delete_payment(payment_id)
