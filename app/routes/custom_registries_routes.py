from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.database import DbAuthSession, DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.custom_registry import (
    AccessCreate, AccessUpdate, BlockCreate, BlockUpdate, FieldCreate, FieldUpdate, LayoutUpdate, RecordValues, RegistryCreate, RegistryUpdate,
)
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.custom_registry_repository import CustomRegistryRepository
from app.repositories.department_repository import DepartmentRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.services.custom_registry_service import CustomRegistryService

custom_registries_router = APIRouter(prefix="/custom-registries", tags=["Custom registries"])


def build_service(supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession) -> CustomRegistryService:
    return CustomRegistryService(CustomRegistryRepository(supply_db), AuthUserRepository(auth_db), ReferenceObjectRepository(reference_db), DepartmentRepository(supply_db))


# --- static paths first ---

@custom_registries_router.get("/access/me", summary="Мои права: можно ли создавать реестры и что можно в каждом реестре")
def my_access(supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db, reference_db).my_access(_session.user_id)


@custom_registries_router.get("/access", summary="Правила доступа к реестрам (администратор)")
def list_access(
    supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session),
    user_id: str | None = Query(default=None), department_id: int | None = Query(default=None),
):
    return build_service(supply_db, auth_db, reference_db).list_access(_session.user_id, user_id, department_id)


@custom_registries_router.post("/access", status_code=status.HTTP_201_CREATED, summary="Выдать права пользователю или отделу (администратор)")
def create_access(payload: AccessCreate, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db, reference_db).create_access(payload, _session.user_id)


@custom_registries_router.patch("/access/{rule_id}", summary="Изменить правило (администратор)")
def update_access(rule_id: str, payload: AccessUpdate, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db, reference_db).update_access(rule_id, payload, _session.user_id)


@custom_registries_router.delete("/access/{rule_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить правило (администратор)")
def delete_access(rule_id: str, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    build_service(supply_db, auth_db, reference_db).delete_access(rule_id, _session.user_id)


@custom_registries_router.get("/meta", summary="Типы полей, которые можно добавить в реестр")
def meta(supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db, reference_db).meta()


@custom_registries_router.patch("/blocks/{block_id}", summary="Переименовать блок")
def update_block(block_id: int, payload: BlockUpdate, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db, reference_db).update_block(block_id, payload, _session.user_id)


@custom_registries_router.delete("/blocks/{block_id}", summary="Удалить блок (его поля остаются, но без блока)")
def delete_block(block_id: int, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db, reference_db).delete_block(block_id, _session.user_id)


@custom_registries_router.patch("/fields/{field_id}", summary="Изменить поле: название, блок, обязательность, варианты")
def update_field(field_id: int, payload: FieldUpdate, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db, reference_db).update_field(field_id, payload, _session.user_id)


@custom_registries_router.delete("/fields/{field_id}", summary="Удалить поле")
def delete_field(field_id: int, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session), force: bool = Query(default=False)):
    return build_service(supply_db, auth_db, reference_db).delete_field(field_id, _session.user_id, force)


@custom_registries_router.get("/records/{record_id}", summary="Запись реестра")
def get_record(record_id: int, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db, reference_db).get_record(record_id, _session.user_id)


@custom_registries_router.patch("/records/{record_id}", summary="Изменить запись (только переданные поля; null - очистить)")
def update_record(record_id: int, payload: RecordValues, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db, reference_db).update_record(record_id, payload, _session.user_id)


@custom_registries_router.delete("/records/{record_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить запись")
def delete_record(record_id: int, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    build_service(supply_db, auth_db, reference_db).delete_record(record_id, _session.user_id)


@custom_registries_router.get("/records/{record_id}/files", summary="Файлы записи")
def get_record_files(record_id: int, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db, reference_db).get_files(record_id, _session.user_id)


@custom_registries_router.post("/records/{record_id}/files", status_code=status.HTTP_201_CREATED, summary="Загрузить файлы в запись (multipart, поле files)")
def upload_record_files(record_id: int, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session), files: list[UploadFile] = File(...)):
    return build_service(supply_db, auth_db, reference_db).upload_files(record_id, files, _session.user_id)


@custom_registries_router.get("/records/{record_id}/history", summary="История записи (в том числе удалённой)")
def get_record_history(record_id: int, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session), limit: int = Query(default=50, ge=1, le=500), offset: int = Query(default=0, ge=0)):
    return build_service(supply_db, auth_db, reference_db).get_record_history(record_id, limit, offset, _session.user_id)


@custom_registries_router.get("/files/{file_id}/download", summary="Скачать файл")
def download_file(file_id: str, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    path, name = build_service(supply_db, auth_db, reference_db).get_file_path(file_id, _session.user_id)
    return FileResponse(path, filename=name)


@custom_registries_router.get("/files/{file_id}/preview", summary="Предпросмотр файла (PDF)")
def preview_file(file_id: str, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return FileResponse(build_service(supply_db, auth_db, reference_db).get_preview(file_id, _session.user_id), media_type="application/pdf")


@custom_registries_router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить файл")
def delete_file(file_id: str, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    build_service(supply_db, auth_db, reference_db).delete_file(file_id, _session.user_id)


# --- registries ---

@custom_registries_router.get("", summary="Список реестров")
def list_registries(supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db, reference_db).list_registries(_session.user_id)


@custom_registries_router.post("", status_code=status.HTTP_201_CREATED, summary="Создать реестр (администратор)")
def create_registry(payload: RegistryCreate, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db, reference_db).create_registry(payload, _session.user_id)


@custom_registries_router.get("/{registry_id}", summary="Реестр со структурой: блоки и поля")
def get_registry(registry_id: int, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db, reference_db).get_registry(registry_id, _session.user_id)


@custom_registries_router.patch("/{registry_id}", summary="Переименовать реестр (администратор)")
def update_registry(registry_id: int, payload: RegistryUpdate, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db, reference_db).update_registry(registry_id, payload, _session.user_id)


@custom_registries_router.delete("/{registry_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить реестр (администратор)")
def delete_registry(registry_id: int, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session), force: bool = Query(default=False)):
    build_service(supply_db, auth_db, reference_db).delete_registry(registry_id, _session.user_id, force)


@custom_registries_router.post("/{registry_id}/blocks", status_code=status.HTTP_201_CREATED, summary="Добавить блок")
def create_block(registry_id: int, payload: BlockCreate, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db, reference_db).create_block(registry_id, payload, _session.user_id)


@custom_registries_router.post("/{registry_id}/fields", status_code=status.HTTP_201_CREATED, summary="Добавить поле")
def create_field(registry_id: int, payload: FieldCreate, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db, reference_db).create_field(registry_id, payload, _session.user_id)


@custom_registries_router.put("/{registry_id}/layout", summary="Порядок блоков и полей, перенос полей между блоками")
def update_layout(registry_id: int, payload: LayoutUpdate, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db, reference_db).update_layout(registry_id, payload, _session.user_id)


@custom_registries_router.get("/{registry_id}/history", summary="История реестра: записи, поля, блоки")
def get_registry_history(registry_id: int, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session), limit: int = Query(default=50, ge=1, le=500), offset: int = Query(default=0, ge=0)):
    return build_service(supply_db, auth_db, reference_db).get_registry_history(registry_id, limit, offset, _session.user_id)


@custom_registries_router.get("/{registry_id}/records", summary="Записи реестра (поиск q, пагинация)")
def list_records(
    registry_id: int, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession,
    _session=Depends(get_session), q: str | None = Query(default=None, description="поиск по значениям полей"),
    limit: int = Query(default=50, ge=1, le=500), offset: int = Query(default=0, ge=0),
):
    return build_service(supply_db, auth_db, reference_db).list_records(registry_id, q, limit, offset, _session.user_id)


@custom_registries_router.post("/{registry_id}/records", status_code=status.HTTP_201_CREATED, summary="Добавить запись в реестр")
def create_record(registry_id: int, payload: RecordValues, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db, reference_db).create_record(registry_id, payload, _session.user_id)
