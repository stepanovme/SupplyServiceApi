from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.database import DbAuthSession, DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.session import SessionDB
from app.models.supply_request import SupplyRequestCreate, SupplyRequestUpdate
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.repositories.request_file_repository import RequestFileRepository
from app.repositories.request_repository import RequestRepository
from app.services.request_file_service import RequestFileService
from app.services.request_service import RequestService

requests_router = APIRouter(prefix="/requests", tags=["Requests"])


def build_request_service(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
) -> RequestService:
    return RequestService(
        RequestRepository(supply_db),
        AuthUserRepository(auth_db),
        ReferenceObjectRepository(reference_db),
    )


@requests_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Получить список всех заявок",
)
def get_all_requests(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_request_service(supply_db, auth_db, reference_db)
    return service.get_all()


@requests_router.get(
    "/my",
    status_code=status.HTTP_200_OK,
    summary="Получить список доступных мне заявок",
)
def get_my_requests(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = build_request_service(supply_db, auth_db, reference_db)
    return service.get_available_for_user(str(session.user_id))


@requests_router.get(
    "/my/{request_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить доступную мне заявку по id",
)
def get_my_request_by_id(
    request_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = build_request_service(supply_db, auth_db, reference_db)
    item = service.get_available_for_user_by_id(str(session.user_id), request_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return item


@requests_router.get(
    "/{request_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить заявку по id",
)
def get_request_by_id(
    request_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_request_service(supply_db, auth_db, reference_db)
    item = service.get_by_id(request_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return item


@requests_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать заявку",
)
def create_request(
    payload: SupplyRequestCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = build_request_service(supply_db, auth_db, reference_db)
    return service.create(payload, str(session.user_id))


@requests_router.patch(
    "/{request_id}",
    status_code=status.HTTP_200_OK,
    summary="Редактировать заявку",
)
def update_request(
    request_id: int,
    payload: SupplyRequestUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_request_service(supply_db, auth_db, reference_db)
    return service.update(request_id, payload)


@requests_router.post(
    "/{request_id}/attachments",
    status_code=status.HTTP_201_CREATED,
    summary="Загрузить файл-приложение к заявке",
)
async def upload_request_attachment(
    request_id: int,
    db: DbSupplySession,
    session: SessionDB = Depends(get_session),
    file: UploadFile = File(...),
):
    service = RequestFileService(RequestFileRepository(db))
    file_bytes = await file.read()
    return service.upload_request_attachment(
        request_id=request_id,
        original_name=file.filename or "file",
        mime_type=file.content_type or "application/octet-stream",
        file_bytes=file_bytes,
        user_id=str(session.user_id),
    )


@requests_router.get(
    "/{request_id}/attachments",
    status_code=status.HTTP_200_OK,
    summary="Получить список файлов заявки",
)
def get_request_attachments(
    request_id: int,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = RequestFileService(RequestFileRepository(db))
    return service.get_request_files(request_id)


@requests_router.get(
    "/{request_id}/attachments/{file_id}/download",
    status_code=status.HTTP_200_OK,
    summary="Скачать файл заявки",
)
def download_request_attachment(
    request_id: int,
    file_id: str,
    db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    service = RequestFileService(RequestFileRepository(db))
    payload = service.get_download_file_payload(request_id, file_id, str(session.user_id))
    return FileResponse(
        path=payload["path"],
        filename=payload["filename"],
        media_type=payload["media_type"],
    )


@requests_router.delete(
    "/{request_id}/attachments/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить файл заявки",
)
def delete_request_attachment(
    request_id: int,
    file_id: str,
    db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    service = RequestFileService(RequestFileRepository(db))
    service.delete_request_file(request_id, file_id, str(session.user_id))
    return None
