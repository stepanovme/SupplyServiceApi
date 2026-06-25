from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import HTMLResponse

from app.database import DbAuthSession, DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.request_supplier import (
    RequestSupplierCreate,
    RequestSupplierLinkCreate,
    RequestSupplierLinkResponse,
    RequestSupplierLinkUpdate,
    RequestSupplierEmailSenderCreate,
    RequestSupplierEmailSenderUpdate,
    RequestSupplierFileUpdate,
    RequestSupplierItemCreate,
    RequestSupplierItemUpdate,
    RequestSupplierRecipientCreate,
    RequestSupplierRecipientUpdate,
    RequestSupplierSendResponse,
    RequestSupplierTestSmtpResponse,
    RequestSupplierUpdate,
)
from app.models.session import SessionDB
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.counterparty_repository import CounterpartyRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.repositories.request_supplier_repository import RequestSupplierRepository
from app.repositories.smtp_repository import SmtpRepository
from app.repositories.warehouse_repository import WarehouseRepository
from app.services.request_supplier_service import RequestSupplierService

request_suppliers_router = APIRouter(prefix="/request-suppliers", tags=["RequestSuppliers"])
public_request_suppliers_router = APIRouter(prefix="/request-suppliers", tags=["RequestSuppliersPublic"])


def build_service(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
) -> RequestSupplierService:
    return RequestSupplierService(
        RequestSupplierRepository(supply_db),
        AuthUserRepository(auth_db),
        CounterpartyRepository(reference_db),
        ReferenceObjectRepository(reference_db),
        WarehouseRepository(supply_db),
        SmtpRepository(supply_db),
    )


@public_request_suppliers_router.get(
    "/link/{code}",
    status_code=status.HTTP_200_OK,
    summary="Получить публичную страницу request_supplier по ссылке",
    response_class=HTMLResponse,
)
def get_request_supplier_public_page(
    code: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
):
    service = build_service(supply_db, auth_db, reference_db)
    return HTMLResponse(service.get_request_supplier_public_page_by_code(code))


@request_suppliers_router.get("", status_code=status.HTTP_200_OK, summary="Получить список request_supplier")
def get_request_suppliers(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_all()


@request_suppliers_router.get("/{request_supplier_id}", status_code=status.HTTP_200_OK, summary="Получить request_supplier по id")
def get_request_supplier_by_id(
    request_supplier_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_by_id(request_supplier_id)


@request_suppliers_router.post("", status_code=status.HTTP_201_CREATED, summary="Создать request_supplier")
def create_request_supplier(
    payload: RequestSupplierCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).create(payload, str(session.user_id))


@request_suppliers_router.patch("/{request_supplier_id}", status_code=status.HTTP_200_OK, summary="Обновить request_supplier")
def update_request_supplier(
    request_supplier_id: str,
    payload: RequestSupplierUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).update(request_supplier_id, payload)


@request_suppliers_router.delete("/{request_supplier_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить request_supplier")
def delete_request_supplier(
    request_supplier_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    build_service(supply_db, auth_db, reference_db).delete(request_supplier_id)
    return None


@request_suppliers_router.get("/{request_supplier_id}/items", status_code=status.HTTP_200_OK, summary="Получить items request_supplier")
def get_request_supplier_items(
    request_supplier_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_items(request_supplier_id)


@request_suppliers_router.post("/{request_supplier_id}/items", status_code=status.HTTP_201_CREATED, summary="Создать item request_supplier")
def create_request_supplier_item(
    request_supplier_id: str,
    payload: RequestSupplierItemCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).create_item(request_supplier_id, payload)


@request_suppliers_router.patch("/{request_supplier_id}/items/{item_id}", status_code=status.HTTP_200_OK, summary="Обновить item request_supplier")
def update_request_supplier_item(
    request_supplier_id: str,
    item_id: str,
    payload: RequestSupplierItemUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).update_item(request_supplier_id, item_id, payload)


@request_suppliers_router.delete("/{request_supplier_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить item request_supplier")
def delete_request_supplier_item(
    request_supplier_id: str,
    item_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    build_service(supply_db, auth_db, reference_db).delete_item(request_supplier_id, item_id)
    return None


@request_suppliers_router.get("/{request_supplier_id}/email-senders", status_code=status.HTTP_200_OK, summary="Получить email senders request_supplier")
def get_request_supplier_email_senders(
    request_supplier_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_email_senders(request_supplier_id)


@request_suppliers_router.post("/{request_supplier_id}/email-senders", status_code=status.HTTP_201_CREATED, summary="Создать email sender request_supplier")
def create_request_supplier_email_sender(
    request_supplier_id: str,
    payload: RequestSupplierEmailSenderCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).create_email_sender(request_supplier_id, payload)


@request_suppliers_router.patch("/{request_supplier_id}/email-senders/{row_id}", status_code=status.HTTP_200_OK, summary="Обновить email sender request_supplier")
def update_request_supplier_email_sender(
    request_supplier_id: str,
    row_id: str,
    payload: RequestSupplierEmailSenderUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).update_email_sender(request_supplier_id, row_id, payload)


@request_suppliers_router.delete("/{request_supplier_id}/email-senders/{row_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить email sender request_supplier")
def delete_request_supplier_email_sender(
    request_supplier_id: str,
    row_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    build_service(supply_db, auth_db, reference_db).delete_email_sender(request_supplier_id, row_id)
    return None


@request_suppliers_router.get("/{request_supplier_id}/files", status_code=status.HTTP_200_OK, summary="Получить файлы request_supplier")
def get_request_supplier_files(
    request_supplier_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_files(request_supplier_id)


@request_suppliers_router.post("/{request_supplier_id}/files", status_code=status.HTTP_201_CREATED, summary="Загрузить файл request_supplier")
async def create_request_supplier_file(
    request_supplier_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    file: Annotated[UploadFile, File(...)],
    session: SessionDB = Depends(get_session),
):
    service = build_service(supply_db, auth_db, reference_db)
    file_bytes = await file.read()
    return service.upload_file(
        request_supplier_id=request_supplier_id,
        original_name=file.filename or "file",
        mime_type=file.content_type or "application/octet-stream",
        file_bytes=file_bytes,
        user_id=str(session.user_id),
    )


@request_suppliers_router.patch("/{request_supplier_id}/files/{row_id}", status_code=status.HTTP_200_OK, summary="Обновить файл request_supplier")
def update_request_supplier_file(
    request_supplier_id: str,
    row_id: str,
    payload: RequestSupplierFileUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).update_file(request_supplier_id, row_id, payload)


@request_suppliers_router.delete("/{request_supplier_id}/files/{row_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить файл request_supplier")
def delete_request_supplier_file(
    request_supplier_id: str,
    row_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    build_service(supply_db, auth_db, reference_db).delete_file(request_supplier_id, row_id)
    return None


@request_suppliers_router.get("/{request_supplier_id}/recipients", status_code=status.HTTP_200_OK, summary="Получить recipients request_supplier")
def get_request_supplier_recipients(
    request_supplier_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_recipients(request_supplier_id)


@request_suppliers_router.post("/{request_supplier_id}/recipients", status_code=status.HTTP_201_CREATED, summary="Создать recipient request_supplier")
def create_request_supplier_recipient(
    request_supplier_id: str,
    payload: RequestSupplierRecipientCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).create_recipient(request_supplier_id, payload)


@request_suppliers_router.patch("/{request_supplier_id}/recipients/{row_id}", status_code=status.HTTP_200_OK, summary="Обновить recipient request_supplier")
def update_request_supplier_recipient(
    request_supplier_id: str,
    row_id: str,
    payload: RequestSupplierRecipientUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).update_recipient(request_supplier_id, row_id, payload)


@request_suppliers_router.delete("/{request_supplier_id}/recipients/{row_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить recipient request_supplier")
def delete_request_supplier_recipient(
    request_supplier_id: str,
    row_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    build_service(supply_db, auth_db, reference_db).delete_recipient(request_supplier_id, row_id)
    return None


@request_suppliers_router.get(
    "/{request_supplier_id}/links",
    status_code=status.HTTP_200_OK,
    summary="Получить links request_supplier",
    response_model=list[RequestSupplierLinkResponse],
)
def get_request_supplier_links(
    request_supplier_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_links(request_supplier_id)


@request_suppliers_router.post(
    "/{request_supplier_id}/links",
    status_code=status.HTTP_201_CREATED,
    summary="Создать link request_supplier",
    response_model=RequestSupplierLinkResponse,
)
def create_request_supplier_link(
    request_supplier_id: str,
    payload: RequestSupplierLinkCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).create_link(request_supplier_id, payload)


@request_suppliers_router.patch(
    "/{request_supplier_id}/links/{row_id}",
    status_code=status.HTTP_200_OK,
    summary="Обновить link request_supplier",
    response_model=RequestSupplierLinkResponse,
)
def update_request_supplier_link(
    request_supplier_id: str,
    row_id: str,
    payload: RequestSupplierLinkUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).update_link(request_supplier_id, row_id, payload)


@request_suppliers_router.delete(
    "/{request_supplier_id}/links/{row_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить link request_supplier",
)
def delete_request_supplier_link(
    request_supplier_id: str,
    row_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    build_service(supply_db, auth_db, reference_db).delete_link(request_supplier_id, row_id)
    return None


@request_suppliers_router.post(
    "/{request_supplier_id}/send",
    status_code=status.HTTP_200_OK,
    summary="Отправить request_supplier по SMTP",
    response_model=RequestSupplierSendResponse,
)
def send_request_supplier(
    request_supplier_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).send(request_supplier_id, str(session.user_id))


@request_suppliers_router.post(
    "/{request_supplier_id}/test-smtp",
    status_code=status.HTTP_200_OK,
    summary="Проверить SMTP для request_supplier без отправки письма",
    response_model=RequestSupplierTestSmtpResponse,
)
def test_request_supplier_smtp(
    request_supplier_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).test_smtp(request_supplier_id)
