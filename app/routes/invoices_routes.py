import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import ValidationError

from app.database import DbAuthSession, DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.invoice import (
    InvoiceCreate,
    InvoiceDuplicateCheckRequest,
    InvoiceLogCreate,
    InvoiceLogUpdate,
    InvoiceItemCreate,
    InvoiceItemUpdate,
    InvoiceParseRequest,
    InvoicePaymentCreate,
    InvoicePaymentUpdate,
    InvoiceUpdate,
    InvoiceClosingDocsMark,
    InvoiceDeliveryMark,
)
from app.models.session import SessionDB
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.counterparty_repository import CounterpartyRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.invoice_user_repository import InvoiceUserRepository
from app.repositories.object_setting_repository import ObjectSettingRepository
from app.repositories.project_user_role_repository import ProjectUserRoleRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.repositories.request_file_repository import RequestFileRepository
from app.services.invoice_service import InvoiceService

invoices_router = APIRouter(prefix="/invoices", tags=["Invoices"])


def build_invoice_service(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
) -> InvoiceService:
    return InvoiceService(
        InvoiceRepository(supply_db),
        RequestFileRepository(supply_db),
        CounterpartyRepository(reference_db),
        AuthUserRepository(auth_db),
        ReferenceObjectRepository(reference_db),
        ProjectUserRoleRepository(supply_db),
        InvoiceUserRepository(supply_db),
        ObjectSettingRepository(supply_db),
    )


@invoices_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Получить список всех счетов",
)
def get_invoices(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    return service.get_all(str(session.user_id))


@invoices_router.get(
    "/my",
    status_code=status.HTTP_200_OK,
    summary="Получить список доступных мне счетов",
)
def get_my_invoices(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    return service.get_available_for_user(str(session.user_id))


@invoices_router.get(
    "/by-object/{object_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить список счетов по объекту",
)
def get_invoices_by_object(
    object_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    return service.get_by_object(object_id)


@invoices_router.get(
    "/my/badge",
    status_code=status.HTTP_200_OK,
    summary="Получить количество счетов требующих действий",
)
def get_my_invoices_badge(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    return service.get_badge_counts(str(session.user_id))


@invoices_router.get(
    "/my/payments",
    status_code=status.HTTP_200_OK,
    summary="Получить платежи по доступным мне счетам",
)
def get_my_invoice_payments(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
    paid: bool | None = Query(default=None, description="true — оплаченные, false — неоплаченные"),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    return service.get_my_invoice_payments(str(session.user_id), paid=paid)


@invoices_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать счет",
)
def create_invoice(
    payload: InvoiceCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    return service.create_invoice(payload, str(session.user_id))


@invoices_router.post(
    "/{invoice_id}/file",
    status_code=status.HTTP_200_OK,
    summary="Загрузить или заменить файл счёта",
)
async def upload_invoice_file(
    invoice_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
    file: UploadFile = File(...),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    file_bytes = await file.read()
    return await run_in_threadpool(
        service.upload_invoice_file,
        invoice_id,
        file_bytes,
        file.filename or "file",
        file.content_type or "application/octet-stream",
        str(session.user_id),
    )


@invoices_router.post(
    "/with-file",
    status_code=status.HTTP_201_CREATED,
    summary="Создать счет сразу с файлом",
)
async def create_invoice_with_file(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
    payload_json: str = Form(...),
    file: UploadFile = File(...),
):
    try:
        payload = InvoiceCreate.model_validate(json.loads(payload_json))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload_json for invoice",
        ) from exc

    service = build_invoice_service(supply_db, auth_db, reference_db)
    file_bytes = await file.read()
    return await run_in_threadpool(
        service.create_invoice_with_file,
        payload,
        str(session.user_id),
        file.filename or "file",
        file.content_type or "application/octet-stream",
        file_bytes,
    )


@invoices_router.patch(
    "/{invoice_id}",
    status_code=status.HTTP_200_OK,
    summary="Редактировать счет",
)
def update_invoice(
    invoice_id: int,
    payload: InvoiceUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    return service.update_invoice(invoice_id, payload)


@invoices_router.patch(
    "/{invoice_id}/closing-docs-mark",
    status_code=status.HTTP_200_OK,
    summary="Поставить/снять маркер «Акты/УПД не требуются»",
)
def set_closing_docs_mark(
    invoice_id: int,
    payload: InvoiceClosingDocsMark,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    return service.set_closing_docs_mark(invoice_id, payload.not_required, str(session.user_id))


@invoices_router.patch(
    "/{invoice_id}/delivery-mark",
    status_code=status.HTTP_200_OK,
    summary="Поставить/снять маркер «Доставка не требуется»",
)
def set_delivery_mark(
    invoice_id: int,
    payload: InvoiceDeliveryMark,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    return service.set_delivery_mark(invoice_id, payload.not_required, str(session.user_id))


@invoices_router.delete(
    "/{invoice_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить счет",
)
def delete_invoice(
    invoice_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    service.delete_invoice(invoice_id)
    return None


@invoices_router.get(
    "/{invoice_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить счет и его позиции",
)
def get_invoice(
    invoice_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    return service.get_invoice(invoice_id, str(session.user_id))


@invoices_router.get(
    "/{invoice_id}/file/download",
    status_code=status.HTTP_200_OK,
    summary="Скачать файл счета",
)
def download_invoice_file(
    invoice_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    payload = service.get_invoice_file_download_payload(invoice_id, str(session.user_id))
    return FileResponse(
        path=payload["path"],
        filename=payload["filename"],
        media_type=payload["media_type"],
    )


@invoices_router.get(
    "/{invoice_id}/file/preview",
    status_code=status.HTTP_200_OK,
    summary="Предпросмотр файла счета (PDF)",
)
def preview_invoice_file(
    invoice_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    file_path = service.get_invoice_file_preview_path(invoice_id)
    return FileResponse(file_path, media_type="application/pdf")


@invoices_router.post(
    "/{invoice_id}/parse-file",
    status_code=status.HTTP_200_OK,
    summary="Распознать счет из файла и заполнить invoice",
)
def parse_invoice_file(
    invoice_id: int,
    payload: InvoiceParseRequest,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    return service.parse_invoice_file_and_update(invoice_id, payload.file_path, str(session.user_id))


@invoices_router.post(
    "/{invoice_id}/parse-file/qwen",
    status_code=status.HTTP_200_OK,
    summary="Распознать счёт через Groq Qwen и заполнить invoice",
)
def parse_invoice_file_qwen(
    invoice_id: int,
    payload: InvoiceParseRequest,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    return service.parse_invoice_file_and_update(invoice_id, payload.file_path, str(session.user_id), provider="groq")


@invoices_router.post(
    "/check-duplicate",
    status_code=status.HTTP_200_OK,
    summary="Проверить счёт на дубликат по num, date, provider_id, payer_id",
)
def check_invoice_duplicate(
    payload: InvoiceDuplicateCheckRequest,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    return service.check_duplicate(payload.num, payload.date, payload.provider_id, payload.payer_id)


@invoices_router.post(
    "/parse-counterparty",
    status_code=status.HTTP_200_OK,
    summary="Распознать ИНН продавца и покупателя из файла и проверить контрагентов в БД",
)
async def parse_counterparty_from_file(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
    file: UploadFile = File(...),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    file_bytes = await file.read()
    return await run_in_threadpool(
        service.parse_counterparty_from_file,
        file_bytes,
        file.filename or "file",
    )


@invoices_router.post(
    "/{invoice_id}/items",
    status_code=status.HTTP_201_CREATED,
    summary="Добавить позицию в счет",
)
def create_invoice_item(
    invoice_id: int,
    payload: InvoiceItemCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    return service.create_invoice_item(invoice_id, payload)


@invoices_router.patch(
    "/{invoice_id}/items/{item_id}",
    status_code=status.HTTP_200_OK,
    summary="Редактировать позицию счета",
)
def update_invoice_item(
    invoice_id: int,
    item_id: str,
    payload: InvoiceItemUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    return service.update_invoice_item(invoice_id, item_id, payload)


@invoices_router.delete(
    "/{invoice_id}/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить позицию счета",
)
def delete_invoice_item(
    invoice_id: int,
    item_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    service.delete_invoice_item(invoice_id, item_id)
    return None


@invoices_router.post(
    "/{invoice_id}/logs",
    status_code=status.HTTP_201_CREATED,
    summary="Добавить запись согласования счета",
)
def create_invoice_log(
    invoice_id: int,
    payload: InvoiceLogCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    return service.create_invoice_log(invoice_id, payload)


@invoices_router.patch(
    "/{invoice_id}/logs/{log_id}",
    status_code=status.HTTP_200_OK,
    summary="Изменить запись согласования счета",
)
def update_invoice_log(
    invoice_id: int,
    log_id: str,
    payload: InvoiceLogUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    return service.update_invoice_log(invoice_id, log_id, payload)


@invoices_router.delete(
    "/{invoice_id}/logs/{log_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить запись согласования счета",
)
def delete_invoice_log(
    invoice_id: int,
    log_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    service.delete_invoice_log(invoice_id, log_id)
    return None


@invoices_router.post(
    "/{invoice_id}/payments",
    status_code=status.HTTP_201_CREATED,
    summary="Добавить оплату счета",
)
def create_invoice_payment(
    invoice_id: int,
    payload: InvoicePaymentCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    return service.create_invoice_payment(invoice_id, payload, str(session.user_id))


@invoices_router.patch(
    "/{invoice_id}/payments/{payment_id}",
    status_code=status.HTTP_200_OK,
    summary="Изменить оплату счета",
)
def update_invoice_payment(
    invoice_id: int,
    payment_id: str,
    payload: InvoicePaymentUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    return service.update_invoice_payment(invoice_id, payment_id, payload, user_id=str(session.user_id))


@invoices_router.delete(
    "/{invoice_id}/payments/{payment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить оплату счета",
)
def delete_invoice_payment(
    invoice_id: int,
    payment_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    service.delete_invoice_payment(invoice_id, payment_id)
    return None


# --- Additional invoice files ---


@invoices_router.get(
    "/{invoice_id}/files",
    status_code=status.HTTP_200_OK,
    summary="Список доп. файлов счета",
)
def get_invoice_additional_files(
    invoice_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    return service.get_invoice_additional_files(invoice_id)


@invoices_router.post(
    "/{invoice_id}/files",
    status_code=status.HTTP_201_CREATED,
    summary="Загрузить доп. файл к счету",
)
async def upload_invoice_additional_file(
    invoice_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
    file: UploadFile = File(...),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    file_bytes = await file.read()
    return service.upload_invoice_additional_file(
        invoice_id=invoice_id,
        file_bytes=file_bytes,
        original_name=file.filename or "file",
        mime_type=file.content_type or "application/octet-stream",
        user_id=str(session.user_id),
    )


@invoices_router.get(
    "/{invoice_id}/files/{invoice_file_id}/download",
    status_code=status.HTTP_200_OK,
    summary="Скачать доп. файл счета",
)
def download_invoice_additional_file(
    invoice_id: int,
    invoice_file_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    payload = service.get_invoice_additional_file_download_payload(
        invoice_id, invoice_file_id, str(session.user_id),
    )
    return FileResponse(
        payload["path"],
        filename=payload["filename"],
        media_type=payload["media_type"],
    )


@invoices_router.delete(
    "/{invoice_id}/files/{invoice_file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить доп. файл счета",
)
def delete_invoice_additional_file(
    invoice_id: int,
    invoice_file_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    service.delete_invoice_additional_file(invoice_id, invoice_file_id, str(session.user_id))
    return None


@invoices_router.get(
    "/{invoice_id}/files/{invoice_file_id}/preview",
    status_code=status.HTTP_200_OK,
    summary="Предпросмотр доп. файла счета (PDF)",
)
def preview_invoice_additional_file(
    invoice_id: int,
    invoice_file_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_invoice_service(supply_db, auth_db, reference_db)
    payload = service.get_invoice_additional_file_download_payload(
        invoice_id, invoice_file_id, str(_session.user_id),
    )
    file_path = payload["path"]

    from pathlib import Path
    import subprocess
    import os

    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return FileResponse(file_path, media_type="application/pdf")

    PREVIEW_EXTENSIONS = {".docx", ".doc", ".xls", ".xlsx", ".pptx"}
    if ext not in PREVIEW_EXTENSIONS:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Preview not supported for this file type")

    cached = Path(file_path).parent / f"{Path(file_path).name}.preview.pdf"
    if cached.exists():
        return FileResponse(str(cached), media_type="application/pdf")

    result = subprocess.run(
        ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", str(cached.parent), file_path],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Conversion failed: {result.stderr.strip()}")

    output_name = f"{Path(file_path).stem}.pdf"
    output_path = cached.parent / output_name
    if output_path.exists():
        os.rename(str(output_path), str(cached))

    if not cached.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Conversion produced no output")

    return FileResponse(str(cached), media_type="application/pdf")
