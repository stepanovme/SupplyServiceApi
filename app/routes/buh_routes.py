from typing import Annotated
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.database import DbAuthSession, DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.buh import BuhAccessCreate, BuhFileUpdate, BuhFolderCreate, BuhFolderUpdate
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.buh_repository import BuhAccessRepository, BuhFileRepository, BuhFolderRepository
from app.repositories.department_repository import DepartmentRepository
from app.services.buh_service import BuhService

buh_router = APIRouter(prefix="/buh", tags=["Buh"])


def build_service(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession | None = None,
) -> BuhService:
    return BuhService(
        BuhFolderRepository(supply_db),
        BuhFileRepository(supply_db),
        BuhAccessRepository(supply_db),
        AuthUserRepository(auth_db) if auth_db else None,
        DepartmentRepository(supply_db),
    )


# --- Folders ---


@buh_router.get("/folders", status_code=status.HTTP_200_OK, summary="Список всех папок (плоский)")
def get_folders(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).get_folders()


@buh_router.get("/folders/tree", status_code=status.HTTP_200_OK, summary="Дерево папок с файлами")
def get_folder_tree(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).get_folder_tree()


@buh_router.get("/folders/{folder_id}", status_code=status.HTTP_200_OK, summary="Информация о папке")
def get_folder(
    folder_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).get_folder(folder_id)


@buh_router.post("/folders", status_code=status.HTTP_201_CREATED, summary="Создать папку")
def create_folder(
    payload: BuhFolderCreate,
    supply_db: DbSupplySession,
    session=Depends(get_session),
):
    return build_service(supply_db).create_folder(payload, str(session.user_id))


@buh_router.patch("/folders/{folder_id}", status_code=status.HTTP_200_OK, summary="Переименовать папку")
def update_folder(
    folder_id: str,
    payload: BuhFolderUpdate,
    supply_db: DbSupplySession,
    session=Depends(get_session),
):
    return build_service(supply_db).update_folder(folder_id, payload, str(session.user_id))


@buh_router.delete("/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить папку и содержимое")
def delete_folder(
    folder_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete_folder(folder_id)
    return None


# --- Files ---


@buh_router.get("/files", status_code=status.HTTP_200_OK, summary="Файлы (корневые или по папке)")
def get_files(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
    folder_id: str | None = Query(default=None),
):
    return build_service(supply_db).get_files(folder_id)


@buh_router.get("/files/my", status_code=status.HTTP_200_OK, summary="Мои файлы (загруженные мной + по доступу)")
def get_my_files(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    session=Depends(get_session),
):
    return build_service(supply_db, auth_db).get_my_files(str(session.user_id))


@buh_router.get("/files/{file_id}", status_code=status.HTTP_200_OK, summary="Информация о файле")
def get_file(
    file_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).get_file(file_id)


@buh_router.patch("/files/{file_id}", status_code=status.HTTP_200_OK, summary="Переименовать файл")
def update_file(
    file_id: str,
    payload: BuhFileUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).update_file(file_id, payload)


@buh_router.post("/files", status_code=status.HTTP_201_CREATED, summary="Загрузить файл(ы)")
async def upload_files(
    files: Annotated[list[UploadFile], File(...)],
    supply_db: DbSupplySession,
    session=Depends(get_session),
    folder_id: str | None = Form(default=None),
):
    service = build_service(supply_db)
    results = []
    for f in files:
        file_bytes = await f.read()
        results.append(service.upload(
            original_name=f.filename or "file",
            mime_type=f.content_type,
            file_bytes=file_bytes,
            user_id=str(session.user_id),
            folder_id=folder_id,
        ))
    return results


@buh_router.get("/files/{file_id}/download", status_code=status.HTTP_200_OK, summary="Скачать файл")
def download_file(
    file_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    file_path, original_name = build_service(supply_db).get_download(file_id)
    return FileResponse(file_path, filename=original_name)


@buh_router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить файл")
def delete_file(
    file_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete_file(file_id)
    return None


# --- Access ---


@buh_router.get("/access", status_code=status.HTTP_200_OK, summary="Список прав доступа")
def get_access_list(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).get_access_list()


@buh_router.post("/access", status_code=status.HTTP_201_CREATED, summary="Предоставить доступ")
def create_access(
    payload: BuhAccessCreate,
    supply_db: DbSupplySession,
    session=Depends(get_session),
):
    return build_service(supply_db).create_access(payload, str(session.user_id))


@buh_router.delete("/access/{access_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Отозвать доступ")
def delete_access(
    access_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete_access(access_id)
    return None


# --- Convert to PDF ---


@buh_router.post("/convert-to-pdf", summary="Конвертировать изображение или Excel в PDF")
async def convert_to_pdf(
    file: UploadFile,
    _session=Depends(get_session),
):
    from fastapi.responses import Response
    from app.services.pdf_converter import get_pdf_bytes
    from urllib.parse import quote

    file_bytes = await file.read()
    pdf_bytes = get_pdf_bytes(file_bytes, file.filename or "file.pdf")
    safe_name = quote(Path(file.filename or "file").stem, safe="") + ".pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{safe_name}"},
    )
