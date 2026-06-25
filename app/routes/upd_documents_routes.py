from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from app.database import DbAuthSession, DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.session import SessionDB
from app.models.upd_document import UpdDocumentItemCreate, UpdDocumentItemUpdate, UpdDocumentUpdate
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.counterparty_repository import CounterpartyRepository
from app.repositories.request_file_repository import RequestFileRepository
from app.repositories.upd_document_repository import UpdDocumentRepository
from app.services.upd_document_service import UpdDocumentService

upd_documents_router = APIRouter(prefix="/upd-documents", tags=["UPD documents"])


def build_upd_document_service(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
) -> UpdDocumentService:
    return UpdDocumentService(
        UpdDocumentRepository(supply_db),
        RequestFileRepository(supply_db),
        CounterpartyRepository(reference_db),
        AuthUserRepository(auth_db),
    )


@upd_documents_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Получить список УПД документов",
)
def get_upd_documents(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    warehouse_id: str | None = Query(
        default=None,
        description="Фильтр по складу",
        examples=["336bc6e3-1273-11f1-aa8c-bc241127d0bd"],
    ),
    _session=Depends(get_session),
):
    service = build_upd_document_service(supply_db, auth_db, reference_db)
    return service.get_all(warehouse_id)


@upd_documents_router.get(
    "/{document_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить УПД документ и его позиции",
)
def get_upd_document(
    document_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_upd_document_service(supply_db, auth_db, reference_db)
    return service.get_document(document_id)


@upd_documents_router.patch(
    "/{document_id}",
    status_code=status.HTTP_200_OK,
    summary="Изменить данные УПД документа",
)
def update_upd_document(
    document_id: str,
    payload: UpdDocumentUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_upd_document_service(supply_db, auth_db, reference_db)
    return service.update_document(document_id, payload)


@upd_documents_router.post(
    "/parse-file",
    status_code=status.HTTP_200_OK,
    summary="Распознать УПД файл и вернуть JSON без записи в БД",
)
async def parse_upd_document_file(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session: SessionDB = Depends(get_session),
    file: UploadFile = File(...),
):
    service = build_upd_document_service(supply_db, auth_db, reference_db)
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty",
        )
    return await run_in_threadpool(
        service.parse_file_only,
        file.filename or "file",
        file_bytes,
    )


@upd_documents_router.post(
    "/{document_id}/reparse-items",
    status_code=status.HTTP_200_OK,
    summary="Удалить все позиции, заново распознать файл и создать позиции УПД",
)
async def reparse_upd_document_items(
    document_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session: SessionDB = Depends(get_session),
):
    service = build_upd_document_service(supply_db, auth_db, reference_db)
    return await run_in_threadpool(service.reparse_document_items, document_id)


@upd_documents_router.post(
    "/with-file",
    status_code=status.HTTP_201_CREATED,
    summary="Создать УПД документ сразу с файлом и распознаванием",
)
async def create_upd_document_with_file(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
    warehouse_id: str | None = Form(default=None),
    provider_id: str | None = Form(default=None),
    payer_id: str | None = Form(default=None),
    file: UploadFile = File(...),
):
    service = build_upd_document_service(supply_db, auth_db, reference_db)
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty",
        )
    return await run_in_threadpool(
        service.create_document_with_file,
        str(session.user_id),
        file.filename or "file",
        file.content_type or "application/octet-stream",
        file_bytes,
        warehouse_id,
        provider_id,
        payer_id,
    )


@upd_documents_router.get(
    "/{document_id}/file/download",
    status_code=status.HTTP_200_OK,
    summary="Скачать файл УПД документа",
)
def download_upd_document_file(
    document_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = build_upd_document_service(supply_db, auth_db, reference_db)
    payload = service.get_file_download_payload(document_id, str(session.user_id))
    return FileResponse(
        path=payload["path"],
        filename=payload["filename"],
        media_type=payload["media_type"],
    )


@upd_documents_router.post(
    "/{document_id}/items",
    status_code=status.HTTP_201_CREATED,
    summary="Добавить позицию в УПД документ",
)
def create_upd_document_item(
    document_id: str,
    payload: UpdDocumentItemCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_upd_document_service(supply_db, auth_db, reference_db)
    return service.create_document_item(document_id, payload)


@upd_documents_router.patch(
    "/{document_id}/items/{item_id}",
    status_code=status.HTTP_200_OK,
    summary="Изменить позицию в УПД документе",
)
def update_upd_document_item(
    document_id: str,
    item_id: str,
    payload: UpdDocumentItemUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_upd_document_service(supply_db, auth_db, reference_db)
    return service.update_document_item(document_id, item_id, payload)


@upd_documents_router.delete(
    "/{document_id}/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить позицию в УПД документе",
)
def delete_upd_document_item(
    document_id: str,
    item_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_upd_document_service(supply_db, auth_db, reference_db)
    service.delete_document_item(document_id, item_id)
    return None


@upd_documents_router.delete(
    "/{document_id}/items",
    status_code=status.HTTP_200_OK,
    summary="Удалить все позиции в УПД документе",
)
def delete_all_upd_document_items(
    document_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_upd_document_service(supply_db, auth_db, reference_db)
    return service.delete_all_document_items(document_id)
