from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.database import DbAuthSession, DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.upd_registry import (
    UpdCreate, UpdFileUpdate, UpdFolderCreate, UpdFolderUpdate, UpdObjectsAdd,
    UpdStatusCreate, UpdUpdate, UpdUserRoleCreate, UpdUserRoleUpdate,
)
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.department_repository import DepartmentRepository
from app.repositories.document_access_setting_repository import DocumentAccessSettingRepository
from app.repositories.documents_list_repository import DocumentsListRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.repositories.upd_registry_repository import UpdRegistryRepository
from app.services.document_access_setting_service import DocumentAccessSettingService
from app.services.upd_registry_service import PARTY_FIELDS, UpdRegistryService

upd_registry_router = APIRouter(prefix="/upd-registry", tags=["UPD registry"])


def build_service(supply_db, auth_db=None, reference_db=None) -> UpdRegistryService:
    return UpdRegistryService(
        UpdRegistryRepository(supply_db),
        AuthUserRepository(auth_db) if auth_db else None,
        ReferenceObjectRepository(reference_db) if reference_db else None,
        DocumentsListRepository(supply_db),
        DepartmentRepository(supply_db),
        DocumentAccessSettingService(DocumentAccessSettingRepository(supply_db)),
    )


# --- list / CRUD (static paths before /{upd_id}) ---

@upd_registry_router.get("", summary="Реестр УПД")
def get_upds(supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session), signed: bool | None = Query(default=None, description="true - только подписанные, false - только неподписанные")):
    return build_service(supply_db, auth_db, reference_db).get_all(signed)


@upd_registry_router.get("/my", summary="Мои УПД (по ролям и настройкам доступа)")
def get_my_upds(supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session), signed: bool | None = Query(default=None)):
    return build_service(supply_db, auth_db, reference_db).get_my(_session.user_id, signed)


@upd_registry_router.get("/by-object/{object_id}", summary="УПД объекта")
def get_upds_by_object(object_id: str, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session), signed: bool | None = Query(default=None)):
    return build_service(supply_db, auth_db, reference_db).get_by_object(object_id, signed)


@upd_registry_router.post("", status_code=status.HTTP_201_CREATED, summary="Добавить УПД")
def create_upd(payload: UpdCreate, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db, reference_db).create(payload, _session.user_id)


@upd_registry_router.post(
    "/with-file", status_code=status.HTTP_201_CREATED, summary="Добавить УПД сразу с файлами",
    description="multipart/form-data: поля УПД (num, date, sum, buyer_id, seller_id, shipper_id, consignee_id, comment, object_id, object_type) и files. Всё необязательно.",
)
def create_upd_with_file(
    supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession,
    _session=Depends(get_session),
    num: str | None = Form(default=None), date: str | None = Form(default=None), sum: float | None = Form(default=None),
    buyer_id: str | None = Form(default=None), seller_id: str | None = Form(default=None),
    shipper_id: str | None = Form(default=None), consignee_id: str | None = Form(default=None),
    comment: str | None = Form(default=None), is_signed: bool = Form(default=False), object_id: str | None = Form(default=None),
    object_type: str | None = Form(default=None), files: list[UploadFile] = File(default=[]),
):
    objects = [{"object_id": object_id, "object_type": object_type}] if object_id and object_type else []
    try:
        payload = UpdCreate(num=num or None, date=date or None, sum=sum, buyer_id=buyer_id or None, seller_id=seller_id or None,
                            shipper_id=shipper_id or None, consignee_id=consignee_id or None, comment=comment, is_signed=is_signed, objects=objects)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    service = build_service(supply_db, auth_db, reference_db)
    created = service.create(payload, _session.user_id)
    for f in files:
        service.upload_file(created["id"], f, _session.user_id)
    return service.get_by_id(created["id"])


# --- user roles (static before /{upd_id}) ---

@upd_registry_router.patch("/user-roles/{role_id}")
def update_user_role(role_id: str, payload: UpdUserRoleUpdate, supply_db: DbSupplySession, _session=Depends(get_session)):
    return build_service(supply_db).update_user_role(role_id, payload)


@upd_registry_router.delete("/user-roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_role(role_id: str, supply_db: DbSupplySession, _session=Depends(get_session)):
    build_service(supply_db).delete_user_role(role_id)


# --- folders ---

@upd_registry_router.get("/folders")
def get_folders(supply_db: DbSupplySession, auth_db: DbAuthSession, _session=Depends(get_session), upd_id: int = Query(...)):
    return build_service(supply_db, auth_db).get_folders(upd_id)


@upd_registry_router.get("/folders/tree")
def get_folder_tree(supply_db: DbSupplySession, auth_db: DbAuthSession, _session=Depends(get_session), upd_id: int = Query(...)):
    return build_service(supply_db, auth_db).get_folder_tree(upd_id)


@upd_registry_router.post("/folders", status_code=status.HTTP_201_CREATED)
def create_folder(payload: UpdFolderCreate, supply_db: DbSupplySession, auth_db: DbAuthSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db).create_folder(payload, _session.user_id)


@upd_registry_router.patch("/folders/{folder_id}")
def update_folder(folder_id: str, payload: UpdFolderUpdate, supply_db: DbSupplySession, auth_db: DbAuthSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db).update_folder(folder_id, payload, _session.user_id)


@upd_registry_router.delete("/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT, description="Вложенные папки и файлы поднимаются на уровень выше.")
def delete_folder(folder_id: str, supply_db: DbSupplySession, _session=Depends(get_session)):
    build_service(supply_db).delete_folder(folder_id)


# --- files ---

@upd_registry_router.post("/files", status_code=status.HTTP_201_CREATED, summary="Загрузить файлы УПД")
def upload_files(
    supply_db: DbSupplySession, auth_db: DbAuthSession, _session=Depends(get_session),
    upd_id: int = Form(...), folder_id: str | None = Form(default=None), type: str | None = Form(default=None),
    files: list[UploadFile] = File(...),
):
    service = build_service(supply_db, auth_db)
    return [service.upload_file(upd_id, f, _session.user_id, folder_id, file_type=type) for f in files]


@upd_registry_router.get("/files")
def get_files(supply_db: DbSupplySession, auth_db: DbAuthSession, _session=Depends(get_session), upd_id: int = Query(...)):
    return build_service(supply_db, auth_db).get_files(upd_id)


@upd_registry_router.get("/files/{file_id}")
def get_file(file_id: str, supply_db: DbSupplySession, auth_db: DbAuthSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db).get_file(file_id)


@upd_registry_router.get("/files/{file_id}/download")
def download_file(file_id: str, supply_db: DbSupplySession, _session=Depends(get_session)):
    path, name = build_service(supply_db).get_download(file_id)
    return FileResponse(path, filename=name)


@upd_registry_router.get("/files/{file_id}/preview")
def preview_file(file_id: str, supply_db: DbSupplySession, _session=Depends(get_session)):
    return FileResponse(build_service(supply_db).get_preview(file_id), media_type="application/pdf")


@upd_registry_router.patch("/files/{file_id}")
def update_file(file_id: str, payload: UpdFileUpdate, supply_db: DbSupplySession, auth_db: DbAuthSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db).update_file(file_id, payload, _session.user_id)


@upd_registry_router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(file_id: str, supply_db: DbSupplySession, _session=Depends(get_session)):
    build_service(supply_db).delete_file(file_id, _session.user_id)


# --- one UPD ---

@upd_registry_router.get("/{upd_id}", summary="УПД с файлами, папками, ролями и статусами")
def get_upd(upd_id: int, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db, reference_db).get_by_id(upd_id)


@upd_registry_router.patch("/{upd_id}", summary="Изменить УПД")
def update_upd(upd_id: int, payload: UpdUpdate, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db, reference_db).update(upd_id, payload, _session.user_id)


@upd_registry_router.delete("/{upd_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить УПД вместе с файлами")
def delete_upd(upd_id: int, supply_db: DbSupplySession, _session=Depends(get_session)):
    build_service(supply_db).delete(upd_id)


@upd_registry_router.get("/{upd_id}/history", summary="История изменений УПД")
def get_history(upd_id: int, supply_db: DbSupplySession, auth_db: DbAuthSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db).get_history(upd_id)


@upd_registry_router.get("/{upd_id}/objects", summary="Объекты УПД")
def get_objects(upd_id: int, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db, reference_db).get_objects(upd_id)


@upd_registry_router.post("/{upd_id}/objects", status_code=status.HTTP_201_CREATED, summary="Добавить объекты к УПД")
def add_objects(upd_id: int, payload: UpdObjectsAdd, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db, reference_db).add_objects(upd_id, payload, _session.user_id)


@upd_registry_router.delete("/{upd_id}/objects/{obj_id}", summary="Убрать объект из УПД")
def delete_object(upd_id: int, obj_id: int, supply_db: DbSupplySession, auth_db: DbAuthSession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db, reference_db).delete_object(upd_id, obj_id, _session.user_id)


@upd_registry_router.get("/{upd_id}/access", summary="Доступ текущего пользователя к УПД (document_access_settings)")
def check_access(upd_id: int, supply_db: DbSupplySession, _session=Depends(get_session)):
    service = build_service(supply_db)
    upd = service.repo.get_by_id(upd_id)
    if not upd:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UPD not found")
    dept_ids = service.department_repo.get_department_ids_for_user(str(_session.user_id))
    parties = [getattr(upd, f) for f in PARTY_FIELDS if getattr(upd, f)]
    return service.doc_access_service.check_document_access("upd", str(_session.user_id), dept_ids, parties)


@upd_registry_router.get("/{upd_id}/user-roles")
def get_user_roles(upd_id: int, supply_db: DbSupplySession, auth_db: DbAuthSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db).get_user_roles(upd_id)


@upd_registry_router.post("/{upd_id}/user-roles", status_code=status.HTTP_201_CREATED)
def create_user_role(upd_id: int, payload: UpdUserRoleCreate, supply_db: DbSupplySession, auth_db: DbAuthSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db).create_user_role(upd_id, payload, _session.user_id)


@upd_registry_router.get("/{upd_id}/statuses")
def get_statuses(upd_id: int, supply_db: DbSupplySession, auth_db: DbAuthSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db).get_statuses(upd_id)


@upd_registry_router.post("/{upd_id}/statuses", status_code=status.HTTP_201_CREATED)
def create_status(upd_id: int, payload: UpdStatusCreate, supply_db: DbSupplySession, auth_db: DbAuthSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db).create_status(upd_id, payload, _session.user_id)
