import os
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse

from app.database import DbAuthSession, DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.letter import (
    LetterCreate,
    LetterFileUpdate,
    LetterFolderCreate,
    LetterFolderUpdate,
    LetterObjectCreate,
    LetterStatusCreate,
    LetterStatusUpdate,
    LetterUpdate,
    LetterUserRoleCreate,
    LetterUserRoleUpdate,
)
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.letter_repository import LetterRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.services.letter_service import BASE_LETTER_FILES_DIR, LetterService

letters_router = APIRouter(prefix="", tags=["Letters"])


def build_service(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession | None = None,
    reference_db: DbReferenceSession | None = None,
) -> LetterService:
    return LetterService(
        LetterRepository(supply_db),
        AuthUserRepository(auth_db) if auth_db else None,
        ReferenceObjectRepository(reference_db) if reference_db else None,
    )


# --- LetterLog ---

@letters_router.get("/letter-logs", status_code=status.HTTP_200_OK)
def get_letter_logs(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
    letter_id: int | None = Query(default=None),
    created_by: str | None = Query(default=None),
):
    return build_service(supply_db, auth_db).get_logs(letter_id, created_by)


# --- LetterObject ---

@letters_router.get("/letter-objects", status_code=status.HTTP_200_OK)
def get_letter_objects(
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
    letter_id: int | None = Query(default=None),
):
    return build_service(supply_db, reference_db=reference_db).get_objects(letter_id)


@letters_router.post("/letter-objects", status_code=status.HTTP_201_CREATED)
def create_letter_object(
    payload: LetterObjectCreate,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, reference_db=reference_db).create_object(payload, _session.user_id)


@letters_router.delete("/letter-objects/{obj_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_letter_object(
    obj_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete_object(obj_id, _session.user_id)
    return None


# --- LetterStatus ---

@letters_router.get("/letter-statuses", status_code=status.HTTP_200_OK)
def get_letter_statuses(
    letter_id: int | None = Query(default=None),
    supply_db: DbSupplySession = None,
    _session=Depends(get_session),
):
    return build_service(supply_db).get_statuses(letter_id)


@letters_router.post("/letter-statuses", status_code=status.HTTP_201_CREATED)
def create_letter_status(
    payload: LetterStatusCreate,
    supply_db: DbSupplySession = None,
    _session=Depends(get_session),
):
    return build_service(supply_db).create_status(payload, _session.user_id)


@letters_router.patch("/letter-statuses/{status_id}", status_code=status.HTTP_200_OK)
def update_letter_status(
    status_id: int,
    payload: LetterStatusUpdate,
    supply_db: DbSupplySession = None,
    _session=Depends(get_session),
):
    return build_service(supply_db).update_status(status_id, payload, _session.user_id)


@letters_router.delete("/letter-statuses/{status_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_letter_status(
    status_id: int,
    supply_db: DbSupplySession = None,
    _session=Depends(get_session),
):
    build_service(supply_db).delete_status(status_id, _session.user_id)
    return None


# --- LetterUserRole ---

@letters_router.get("/letter-user-roles", status_code=status.HTTP_200_OK)
def get_letter_user_roles(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
    letter_id: int | None = Query(default=None),
):
    return build_service(supply_db, auth_db).get_user_roles(letter_id)


@letters_router.get("/letter-user-roles/{role_id}", status_code=status.HTTP_200_OK)
def get_letter_user_role(
    role_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).get_user_role(role_id)


@letters_router.post("/letter-user-roles", status_code=status.HTTP_201_CREATED)
def create_letter_user_role(
    payload: LetterUserRoleCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).create_user_role(payload, _session.user_id)


@letters_router.patch("/letter-user-roles/{role_id}", status_code=status.HTTP_200_OK)
def update_letter_user_role(
    role_id: str,
    payload: LetterUserRoleUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).update_user_role(role_id, payload, _session.user_id)


@letters_router.delete("/letter-user-roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_letter_user_role(
    role_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete_user_role(role_id, _session.user_id)
    return None


# --- Letter ---

@letters_router.get("/letters", status_code=status.HTTP_200_OK)
def get_letters(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
    type: str | None = Query(default=None),
):
    return build_service(supply_db, auth_db, reference_db).get_letters(type)


@letters_router.get("/letters/my", status_code=status.HTTP_200_OK)
def get_my_letters(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
    type: str | None = Query(default=None),
):
    return build_service(supply_db, auth_db, reference_db).get_my_letters(_session.user_id, type)


@letters_router.get("/letters/{letter_id}", status_code=status.HTTP_200_OK)
def get_letter(
    letter_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_letter(letter_id)


@letters_router.post("/letters", status_code=status.HTTP_201_CREATED)
def create_letter(
    payload: LetterCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).create_letter(payload, _session.user_id)


@letters_router.patch("/letters/{letter_id}", status_code=status.HTTP_200_OK)
def update_letter(
    letter_id: int,
    payload: LetterUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).update_letter(letter_id, payload, _session.user_id)


@letters_router.delete("/letters/{letter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_letter(
    letter_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete_letter(letter_id, _session.user_id)
    return None


# --- Editor ---

@letters_router.get("/letters/{letter_id}/editor-config", status_code=status.HTTP_200_OK)
def get_editor_config(
    letter_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
    file_id: str | None = Query(default=None),
):
    return build_service(supply_db, auth_db, reference_db).get_editor_config(letter_id, file_id)


@letters_router.post("/letters/{letter_id}/editor-forcesave", status_code=status.HTTP_200_OK)
def editor_forcesave(
    letter_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).force_save(letter_id)


@letters_router.get("/letters/{letter_id}/template-data", status_code=status.HTTP_200_OK)
def get_letter_template_data(
    letter_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_template_data(letter_id)


@letters_router.post("/letters/{letter_id}/editor-callback", status_code=status.HTTP_200_OK)
def editor_callback(
    letter_id: int,
    body: dict,
    supply_db: DbSupplySession,
):
    status_val = body.get("status")
    url = body.get("url", "")
    token = body.get("token", "")
    print(f"[editor-callback] letter_id={letter_id} status={status_val} url={'set' if url else 'empty'}")
    return build_service(supply_db).handle_editor_callback(letter_id, status_val, url, "00000000-0000-0000-0000-000000000000", token)


@letters_router.get("/letter-editor-files/{letter_id}/{filename}", status_code=status.HTTP_200_OK)
def serve_editor_file(
    letter_id: int,
    filename: str,
    supply_db: DbSupplySession,
):
    file_path = os.path.join(BASE_LETTER_FILES_DIR, str(letter_id), filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    return FileResponse(file_path, filename=filename)


# --- LetterFolder ---

@letters_router.get("/letter-folders", status_code=status.HTTP_200_OK)
def get_letter_folders(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
    letter_id: int | None = Query(default=None),
):
    return build_service(supply_db).get_folders(letter_id)


@letters_router.get("/letter-folders/tree", status_code=status.HTTP_200_OK)
def get_letter_folder_tree(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
    letter_id: int = Query(...),
):
    return build_service(supply_db).get_folder_tree(letter_id)


@letters_router.get("/letter-folders/{folder_id}", status_code=status.HTTP_200_OK)
def get_letter_folder(
    folder_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).get_folder(folder_id)


@letters_router.post("/letter-folders", status_code=status.HTTP_201_CREATED)
def create_letter_folder(
    payload: LetterFolderCreate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).create_folder(payload, _session.user_id)


@letters_router.patch("/letter-folders/{folder_id}", status_code=status.HTTP_200_OK)
def update_letter_folder(
    folder_id: str,
    payload: LetterFolderUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).update_folder(folder_id, payload, _session.user_id)


@letters_router.delete("/letter-folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_letter_folder(
    folder_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete_folder(folder_id, _session.user_id)
    return None


# --- LetterFile ---

@letters_router.get("/letter-files", status_code=status.HTTP_200_OK)
def get_letter_files(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
    letter_id: int | None = Query(default=None),
    folder_id: str | None = Query(default=None),
):
    return build_service(supply_db).get_files(letter_id, folder_id)


@letters_router.get("/letter-files/my", status_code=status.HTTP_200_OK)
def get_my_letter_files(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).get_my_files(_session.user_id)


@letters_router.get("/letter-files/history", status_code=status.HTTP_200_OK)
def get_letter_files_history(
    letter_id: int = Query(...),
    supply_db: DbSupplySession = None,
    _session=Depends(get_session),
):
    return build_service(supply_db).get_files_history(letter_id)


@letters_router.get("/letter-files/{file_id}", status_code=status.HTTP_200_OK)
def get_letter_file(
    file_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).get_file(file_id)


@letters_router.post("/letter-files", status_code=status.HTTP_201_CREATED)
async def upload_letter_files(
    files: Annotated[list[UploadFile], File(...)],
    supply_db: DbSupplySession,
    _session=Depends(get_session),
    letter_id: int = Form(...),
    letter_folder_id: str | None = Form(default=None),
    type: str | None = Form(default=None),
):
    service = build_service(supply_db)
    results = []
    for f in files:
        file_bytes = await f.read()
        results.append(service.upload(
            letter_id=letter_id,
            letter_folder_id=letter_folder_id,
            original_name=f.filename or "file",
            file_bytes=file_bytes,
            uploaded_by=_session.user_id,
            file_type=type,
        ))
    return results


@letters_router.patch("/letter-files/{file_id}", status_code=status.HTTP_200_OK)
def update_letter_file(
    file_id: str,
    payload: LetterFileUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).update_file(file_id, payload, _session.user_id)


@letters_router.delete("/letter-files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_letter_file(
    file_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete_file(file_id, _session.user_id)
    return None


@letters_router.get("/letter-files/{file_id}/download", status_code=status.HTTP_200_OK)
def download_letter_file(
    file_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    file_path, original_name = build_service(supply_db).get_download(file_id)
    return FileResponse(file_path, filename=original_name)


@letters_router.get("/letter-files/{file_id}/preview", status_code=status.HTTP_200_OK)
def preview_letter_file(
    file_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    file_path = build_service(supply_db).get_preview(file_id)
    return FileResponse(file_path, media_type="application/pdf")
