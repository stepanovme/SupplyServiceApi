from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, Query, status
from fastapi.responses import FileResponse

from app.database import DbAuthSession, DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.session import SessionDB
from app.models.specification import (
    SpecificationCreate,
    SpecificationFileUpdate,
    SpecificationItemCreate,
    SpecificationItemUpdate,
    SpecificationSummaryResponse,
    SpecificationUpdate,
)
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.repositories.specification_repository import SpecificationRepository
from app.services.specification_service import SpecificationService

specifications_router = APIRouter(prefix="/specifications", tags=["Specifications"])


def build_service(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
) -> SpecificationService:
    return SpecificationService(
        SpecificationRepository(supply_db),
        AuthUserRepository(auth_db),
        ReferenceObjectRepository(reference_db),
    )


@specifications_router.get("", status_code=status.HTTP_200_OK, summary="Получить список specification")
def get_specifications(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    object_levels_id: str | None = Query(default=None),
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_all(object_levels_id)


@specifications_router.get("/by-object-levels/{object_levels_id}", status_code=status.HTTP_200_OK, summary="Получить specification по object_levels_id")
def get_specifications_by_object_levels_id(
    object_levels_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    status_id: str | None = Query(default=None),
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_by_object_levels_id(object_levels_id, status_id)


@specifications_router.get("/{specification_id}", status_code=status.HTTP_200_OK, summary="Получить specification по id")
def get_specification_by_id(
    specification_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_by_id(specification_id)


@specifications_router.post("", status_code=status.HTTP_201_CREATED, summary="Создать specification")
def create_specification(
    payload: SpecificationCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).create(payload, str(session.user_id))


@specifications_router.patch("/{specification_id}", status_code=status.HTTP_200_OK, summary="Обновить specification")
def update_specification(
    specification_id: str,
    payload: SpecificationUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).update(specification_id, payload)


@specifications_router.delete("/{specification_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить specification")
def delete_specification(
    specification_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    build_service(supply_db, auth_db, reference_db).delete(specification_id)
    return None


@specifications_router.get("/{specification_id}/files", status_code=status.HTTP_200_OK, summary="Получить файлы specification")
def get_specification_files(
    specification_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_files(specification_id)


@specifications_router.post("/{specification_id}/files", status_code=status.HTTP_201_CREATED, summary="Загрузить файл specification")
async def create_specification_file(
    specification_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    file: Annotated[UploadFile, File(...)],
    session: SessionDB = Depends(get_session),
):
    service = build_service(supply_db, auth_db, reference_db)
    file_bytes = await file.read()
    return service.upload_file(
        specification_id=specification_id,
        original_name=file.filename or "file",
        file_bytes=file_bytes,
        user_id=str(session.user_id),
    )


@specifications_router.patch("/{specification_id}/files/{file_id}", status_code=status.HTTP_200_OK, summary="Обновить файл specification")
def update_specification_file(
    specification_id: str,
    file_id: str,
    payload: SpecificationFileUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).update_file(specification_id, file_id, payload)


@specifications_router.delete("/{specification_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить файл specification")
def delete_specification_file(
    specification_id: str,
    file_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    build_service(supply_db, auth_db, reference_db).delete_file(specification_id, file_id)
    return None


@specifications_router.get("/{specification_id}/files/{file_id}/download", status_code=status.HTTP_200_OK, summary="Скачать файл specification")
def download_specification_file(
    specification_id: str,
    file_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    file_path, filename = build_service(supply_db, auth_db, reference_db).get_file_download(specification_id, file_id)
    return FileResponse(file_path, filename=filename)


@specifications_router.get("/{specification_id}/items", status_code=status.HTTP_200_OK, summary="Получить items specification")
def get_specification_items(
    specification_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_items(specification_id)


@specifications_router.get(
    "/{specification_id}/summary",
    status_code=status.HTTP_200_OK,
    summary="Получить сводку по спецификации (заказано / на складе)",
    response_model=list[SpecificationSummaryResponse],
)
def get_specification_summary(
    specification_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_summary(specification_id)


@specifications_router.get("/{specification_id}/items/{item_id}", status_code=status.HTTP_200_OK, summary="Получить item specification")
def get_specification_item_by_id(
    specification_id: str,
    item_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_item_by_id(specification_id, item_id)


@specifications_router.post("/{specification_id}/items", status_code=status.HTTP_201_CREATED, summary="Создать item specification")
def create_specification_item(
    specification_id: str,
    payload: SpecificationItemCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).create_item(specification_id, payload, str(session.user_id))


@specifications_router.patch("/{specification_id}/items/{item_id}", status_code=status.HTTP_200_OK, summary="Обновить item specification")
def update_specification_item(
    specification_id: str,
    item_id: str,
    payload: SpecificationItemUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).update_item(specification_id, item_id, payload)


@specifications_router.delete("/{specification_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить item specification")
def delete_specification_item(
    specification_id: str,
    item_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    build_service(supply_db, auth_db, reference_db).delete_item(specification_id, item_id)
    return None
