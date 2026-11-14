from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.database import DbAuthSession, DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.act import (
    ActCreate,
    ActObjectsAdd,
    ActTypeCreate,
    ActFileUpdate,
    ActFolderCreate,
    ActFolderUpdate,
    ActStatusCreate,
    ActUpdate,
    ActUserRoleCreate,
    ActUserRoleUpdate,
)
from app.repositories.act_repository import ActRepository
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.department_repository import DepartmentRepository
from app.repositories.document_access_setting_repository import DocumentAccessSettingRepository
from app.repositories.documents_list_repository import DocumentsListRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.services.act_service import ActService
from app.services.document_access_setting_service import DocumentAccessSettingService

act_router = APIRouter(prefix="/acts", tags=["Acts"])
act_media_router = APIRouter(prefix="/media/acts", tags=["Acts"])


def build_service(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession | None = None,
    reference_db: DbReferenceSession | None = None,
) -> ActService:
    return ActService(
        ActRepository(supply_db),
        AuthUserRepository(auth_db) if auth_db else None,
        ReferenceObjectRepository(reference_db) if reference_db else None,
        DocumentsListRepository(supply_db),
        DepartmentRepository(supply_db),
        DocumentAccessSettingService(DocumentAccessSettingRepository(supply_db)),
    )


# --- Types ---

@act_router.get("/types", status_code=status.HTTP_200_OK)
def get_act_types(supply_db: DbSupplySession):
    return build_service(supply_db).get_act_types()


@act_router.post("/types", status_code=status.HTTP_201_CREATED)
def create_act_type(
    payload: ActTypeCreate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).create_act_type(payload, _session.user_id)


# --- CRUD (static paths before parameterized) ---

@act_router.get("/my", status_code=status.HTTP_200_OK)
def get_my_acts(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_my(_session.user_id)


@act_router.get(
    "/by-contract/{contract_id}",
    status_code=status.HTTP_200_OK,
    summary="Акты, привязанные к договору (documents_links)",
    description=(
        "Акты, связанные с договором через documents_links (в любом порядке записи связи), в том же виде, "
        "что и список актов GET /acts: тип, номер, полное название, дата, сумма, объект, заказчик, подрядчик, "
        "статус, автор. Дополнительно: documents_link_id, linked_at, linked_by — какая связь привела к акту. "
        "Договора нет — 404; актов нет — []."
    ),
)
def get_acts_by_contract(
    contract_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_by_contract(contract_id)


@act_router.get("", status_code=status.HTTP_200_OK)
def get_acts(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_all()


@act_router.get("/{act_id}", status_code=status.HTTP_200_OK)
def get_act(
    act_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_by_id(act_id)


@act_router.get("/{act_id}/objects", status_code=status.HTTP_200_OK, summary="Объекты акта")
def get_act_objects(
    act_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_objects(act_id)


@act_router.post(
    "/{act_id}/objects",
    status_code=status.HTTP_201_CREATED,
    summary="Добавить к акту один или несколько объектов",
    description="Тело: {\"objects\": [{\"object_id\": \"...\", \"object_type\": \"object\"}, ...]}. Уже добавленные объекты пропускаются. Возвращает полный список объектов акта.",
)
def add_act_objects(
    act_id: int,
    payload: ActObjectsAdd,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).add_objects(act_id, payload, _session.user_id)


@act_router.delete(
    "/{act_id}/objects/{obj_id}",
    status_code=status.HTTP_200_OK,
    summary="Убрать объект из акта",
    description="Если это был основной объект акта (object_id/object_type), основным становится следующий. Возвращает оставшиеся объекты.",
)
def delete_act_object(
    act_id: int,
    obj_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).delete_object(act_id, obj_id, _session.user_id)


@act_router.get("/{act_id}/access", status_code=status.HTTP_200_OK)
def check_act_access(
    act_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_service(supply_db, auth_db, reference_db)
    act = service.repo.get_by_id(act_id)
    if not act:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Act not found")
    dept_repo = service.department_repo
    doc_access = service.doc_access_service
    dept_ids = dept_repo.get_department_ids_for_user(str(_session.user_id)) if dept_repo else []
    counterparty_ids = [act.customer_id, act.contractor_id]
    return doc_access.check_document_access(
        "act", str(_session.user_id), dept_ids, counterparty_ids,
    )


@act_router.post("", status_code=status.HTTP_201_CREATED)
def create_act(
    payload: ActCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).create(payload, _session.user_id)


@act_router.patch("/{act_id}", status_code=status.HTTP_200_OK)
def update_act(
    act_id: int,
    payload: ActUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).update(act_id, payload, _session.user_id)


@act_router.delete("/{act_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_act(
    act_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete(act_id)
    return None


# --- User roles ---

@act_router.get("/{act_id}/user-roles", status_code=status.HTTP_200_OK)
def get_user_roles(
    act_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).get_user_roles(act_id)


@act_router.post("/{act_id}/user-roles", status_code=status.HTTP_201_CREATED)
def create_user_role(
    act_id: int,
    payload: ActUserRoleCreate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).create_user_role(act_id, payload, _session.user_id)


@act_router.patch("/user-roles/{role_id}", status_code=status.HTTP_200_OK)
def update_user_role(
    role_id: str,
    payload: ActUserRoleUpdate,
    supply_db: DbSupplySession,
):
    return build_service(supply_db).update_user_role(role_id, payload)


@act_router.delete("/user-roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_role(
    role_id: str,
    supply_db: DbSupplySession,
):
    build_service(supply_db).delete_user_role(role_id)
    return None


# --- Statuses ---

@act_router.get("/{act_id}/statuses", status_code=status.HTTP_200_OK)
def get_statuses(
    act_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).get_statuses(act_id)


@act_router.post("/{act_id}/statuses", status_code=status.HTTP_201_CREATED)
def create_status(
    act_id: int,
    payload: ActStatusCreate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).create_status(act_id, payload, _session.user_id)


# --- Folders ---

@act_router.get("/act-folders", status_code=status.HTTP_200_OK)
def get_folders(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
    act_id: int = Query(...),
):
    return build_service(supply_db, auth_db).get_folders(act_id)


@act_router.post("/act-folders", status_code=status.HTTP_201_CREATED)
def create_folder(
    payload: ActFolderCreate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).create_folder(payload, _session.user_id)


@act_router.get("/act-folders/tree", status_code=status.HTTP_200_OK)
def get_folder_tree(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
    act_id: int = Query(...),
):
    return build_service(supply_db, auth_db).get_folder_tree(act_id)


@act_router.patch("/act-folders/{folder_id}", status_code=status.HTTP_200_OK)
def update_folder(
    folder_id: str,
    payload: ActFolderUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).update_folder(folder_id, payload, _session.user_id)


@act_router.delete("/act-folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(
    folder_id: str,
    supply_db: DbSupplySession,
):
    build_service(supply_db).delete_folder(folder_id)
    return None


# --- Files ---

@act_router.post("/act-files", status_code=status.HTTP_201_CREATED)
def upload_file(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
    act_id: int = Form(...),
    act_folder_id: str | None = Form(default=None),
    type: str | None = Form(default=None),
    files: list[UploadFile] = File(...),
):
    service = build_service(supply_db)
    results = []
    for f in files:
        results.append(service.upload_file(act_id, f, _session.user_id, act_folder_id, file_type=type))
    return results


@act_router.get("/act-files", status_code=status.HTTP_200_OK)
def get_files(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
    act_id: int = Query(...),
):
    return build_service(supply_db, auth_db).get_files(act_id)


@act_router.get("/act-files/history", status_code=status.HTTP_200_OK)
def get_files_history(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
    act_id: int = Query(...),
):
    return build_service(supply_db, auth_db).get_files_history(act_id)


@act_router.get("/act-files/{file_id}", status_code=status.HTTP_200_OK)
def get_file(
    file_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).get_file(file_id)


@act_router.get("/act-files/{file_id}/download", status_code=status.HTTP_200_OK)
def download_file(
    file_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    file_path, original_name = build_service(supply_db).get_download(file_id)
    return FileResponse(file_path, filename=original_name)


@act_router.get("/act-files/{file_id}/preview", status_code=status.HTTP_200_OK)
def preview_file(
    file_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    file_path = build_service(supply_db).get_preview(file_id)
    return FileResponse(file_path, media_type="application/pdf")


@act_router.patch("/act-files/{file_id}", status_code=status.HTTP_200_OK)
def update_file(
    file_id: str,
    payload: ActFileUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).update_file(file_id, payload, _session.user_id)


@act_router.delete("/act-files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(
    file_id: str,
    supply_db: DbSupplySession,
):
    build_service(supply_db).delete_file(file_id)
    return None


# --- Media ---

@act_media_router.get("/{filename}", status_code=status.HTTP_200_OK)
def get_media(filename: str, supply_db: DbSupplySession):
    file_path = f"{'/home/webserver/models/supply/acts'}/{filename}"
    return FileResponse(file_path)
