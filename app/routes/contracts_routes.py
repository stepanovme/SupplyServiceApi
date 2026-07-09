from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.database import DbAuthSession, DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.contract import (
    ContractCreate,
    ContractFileUpdate,
    ContractFolderCreate,
    ContractFolderUpdate,
    ContractObjectCreate,
    ContractObjectUpdate,
    ContractPartyCreate,
    ContractPartyUpdate,
    ContractStatusCreate,
    ContractStatusUpdate,
    ContractUpdate,
    ContractUserRoleCreate,
    ContractUserRoleUpdate,
    ContractWorkTypeCreate,
    ContractWorkTypeUpdate,
    DocumentTypeCreate,
    DocumentTypeUpdate,
    WorkContractCreate,
)
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.contract_repository import ContractRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.services.contract_service import ContractService

contracts_router = APIRouter(prefix="", tags=["Contracts"])


def build_service(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession | None = None,
    reference_db: DbReferenceSession | None = None,
) -> ContractService:
    return ContractService(
        ContractRepository(supply_db),
        AuthUserRepository(auth_db) if auth_db else None,
        ReferenceObjectRepository(reference_db) if reference_db else None,
    )


# --- ContractWorkType ---

@contracts_router.get("/contract-work-types", status_code=status.HTTP_200_OK)
def get_work_types(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).get_work_types()


@contracts_router.get("/contract-work-types/{work_type_id}", status_code=status.HTTP_200_OK)
def get_work_type(
    work_type_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).get_work_type(work_type_id)


@contracts_router.post("/contract-work-types", status_code=status.HTTP_201_CREATED)
def create_work_type(
    payload: ContractWorkTypeCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).create_work_type(payload, _session.user_id)


@contracts_router.patch("/contract-work-types/{work_type_id}", status_code=status.HTTP_200_OK)
def update_work_type(
    work_type_id: int,
    payload: ContractWorkTypeUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).update_work_type(work_type_id, payload, _session.user_id)


@contracts_router.delete("/contract-work-types/{work_type_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work_type(
    work_type_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete_work_type(work_type_id, _session.user_id)
    return None


# --- DocumentType ---

@contracts_router.get("/document-types", status_code=status.HTTP_200_OK)
def get_document_types(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).get_document_types()


@contracts_router.get("/document-types/{doc_type_id}", status_code=status.HTTP_200_OK)
def get_document_type(
    doc_type_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).get_document_type(doc_type_id)


@contracts_router.post("/document-types", status_code=status.HTTP_201_CREATED)
def create_document_type(
    payload: DocumentTypeCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).create_document_type(payload, _session.user_id)


@contracts_router.patch("/document-types/{doc_type_id}", status_code=status.HTTP_200_OK)
def update_document_type(
    doc_type_id: str,
    payload: DocumentTypeUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).update_document_type(doc_type_id, payload, _session.user_id)


@contracts_router.delete("/document-types/{doc_type_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document_type(
    doc_type_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete_document_type(doc_type_id, _session.user_id)
    return None


# --- ContractLog ---

@contracts_router.get("/contract-logs", status_code=status.HTTP_200_OK)
def get_logs(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
    log_object_id: str | None = Query(default=None),
    log_object_type: str | None = Query(default=None),
    created_by: str | None = Query(default=None),
):
    return build_service(supply_db, auth_db).get_logs(log_object_id, log_object_type, created_by)


# --- ContractParty ---

@contracts_router.get("/contract-parties", status_code=status.HTTP_200_OK)
def get_parties(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
    contract_id: int | None = Query(default=None),
):
    return build_service(supply_db, auth_db, reference_db).get_parties(contract_id)


@contracts_router.get("/contract-parties/{party_id}", status_code=status.HTTP_200_OK)
def get_party(
    party_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_party(party_id)


@contracts_router.post("/contract-parties", status_code=status.HTTP_201_CREATED)
def create_party(
    payload: ContractPartyCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).create_party(payload, _session.user_id)


@contracts_router.patch("/contract-parties/{party_id}", status_code=status.HTTP_200_OK)
def update_party(
    party_id: str,
    payload: ContractPartyUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).update_party(party_id, payload, _session.user_id)


@contracts_router.delete("/contract-parties/{party_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_party(
    party_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete_party(party_id, _session.user_id)
    return None


# --- ContractUserRole ---

@contracts_router.get("/contract-user-roles", status_code=status.HTTP_200_OK)
def get_user_roles(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
    contract_id: int | None = Query(default=None),
):
    return build_service(supply_db, auth_db).get_user_roles(contract_id)


@contracts_router.get("/contract-user-roles/{role_id}", status_code=status.HTTP_200_OK)
def get_user_role(
    role_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).get_user_role(role_id)


@contracts_router.post("/contract-user-roles", status_code=status.HTTP_201_CREATED)
def create_user_role(
    payload: ContractUserRoleCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).create_user_role(payload, _session.user_id)


@contracts_router.patch("/contract-user-roles/{role_id}", status_code=status.HTTP_200_OK)
def update_user_role(
    role_id: str,
    payload: ContractUserRoleUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).update_user_role(role_id, payload, _session.user_id)


@contracts_router.delete("/contract-user-roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_role(
    role_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete_user_role(role_id, _session.user_id)
    return None


# --- WorkContract ---

@contracts_router.get("/work-contracts", status_code=status.HTTP_200_OK)
def get_work_contracts(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
    contract_id: int | None = Query(default=None),
):
    return build_service(supply_db, auth_db).get_work_contracts(contract_id)


@contracts_router.get("/work-contracts/{wc_id}", status_code=status.HTTP_200_OK)
def get_work_contract(
    wc_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).get_work_contract(wc_id)


@contracts_router.post("/work-contracts", status_code=status.HTTP_201_CREATED)
def create_work_contract(
    payload: WorkContractCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).create_work_contract(payload, _session.user_id)


@contracts_router.delete("/work-contracts/{wc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work_contract(
    wc_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete_work_contract(wc_id, _session.user_id)
    return None


# --- ContractObject ---

@contracts_router.get("/contract-objects", status_code=status.HTTP_200_OK)
def get_contract_objects(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
    contract_id: int | None = Query(default=None),
):
    return build_service(supply_db).get_contract_objects(contract_id)


@contracts_router.get("/contract-objects/{obj_id}", status_code=status.HTTP_200_OK)
def get_contract_object(
    obj_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).get_contract_object(obj_id)


@contracts_router.post("/contract-objects", status_code=status.HTTP_201_CREATED)
def create_contract_object(
    payload: ContractObjectCreate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).create_contract_object(payload, _session.user_id)


@contracts_router.patch("/contract-objects/{obj_id}", status_code=status.HTTP_200_OK)
def update_contract_object(
    obj_id: int,
    payload: ContractObjectUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).update_contract_object(obj_id, payload)


@contracts_router.delete("/contract-objects/{obj_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contract_object(
    obj_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete_contract_object(obj_id, _session.user_id)
    return None


# --- ContractStatus ---

@contracts_router.get("/contract-statuses", status_code=status.HTTP_200_OK)
def get_contract_statuses(
    contract_id: int | None = Query(default=None),
    supply_db: DbSupplySession = None,
    _session=Depends(get_session),
):
    return build_service(supply_db).get_contract_statuses(contract_id)


@contracts_router.post("/contract-statuses", status_code=status.HTTP_201_CREATED)
def create_contract_status(
    payload: ContractStatusCreate,
    supply_db: DbSupplySession = None,
    _session=Depends(get_session),
):
    return build_service(supply_db).create_contract_status(payload, _session.user_id)


@contracts_router.patch("/contract-statuses/{status_id}", status_code=status.HTTP_200_OK)
def update_contract_status(
    status_id: str,
    payload: ContractStatusUpdate,
    supply_db: DbSupplySession = None,
    _session=Depends(get_session),
):
    return build_service(supply_db).update_contract_status(status_id, payload, _session.user_id)


@contracts_router.delete("/contract-statuses/{status_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contract_status(
    status_id: str,
    supply_db: DbSupplySession = None,
    _session=Depends(get_session),
):
    build_service(supply_db).delete_contract_status(status_id, _session.user_id)
    return None


# --- Contract ---

@contracts_router.get("/contracts", status_code=status.HTTP_200_OK)
def get_contracts(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_contracts()


@contracts_router.get("/contracts/my", status_code=status.HTTP_200_OK)
def get_my_contracts(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_my_contracts(_session.user_id)


@contracts_router.get("/contracts/{contract_id}", status_code=status.HTTP_200_OK)
def get_contract(
    contract_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_contract(contract_id)


@contracts_router.post("/contracts", status_code=status.HTTP_201_CREATED)
def create_contract(
    payload: ContractCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).create_contract(payload, _session.user_id)


@contracts_router.patch("/contracts/{contract_id}", status_code=status.HTTP_200_OK)
def update_contract(
    contract_id: int,
    payload: ContractUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).update_contract(contract_id, payload, _session.user_id)


@contracts_router.delete("/contracts/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contract(
    contract_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete_contract(contract_id, _session.user_id)
    return None


# --- ContractFolder ---

@contracts_router.get("/contract-folders", status_code=status.HTTP_200_OK)
def get_folders(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
    contract_id: int | None = Query(default=None),
):
    return build_service(supply_db, auth_db).get_folders(contract_id)


@contracts_router.get("/contract-folders/tree", status_code=status.HTTP_200_OK)
def get_folder_tree(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
    contract_id: int = Query(...),
):
    return build_service(supply_db, auth_db).get_folder_tree(contract_id)


@contracts_router.get("/contract-folders/{folder_id}", status_code=status.HTTP_200_OK)
def get_folder(
    folder_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).get_folder(folder_id)


@contracts_router.post("/contract-folders", status_code=status.HTTP_201_CREATED)
def create_folder(
    payload: ContractFolderCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).create_folder(payload, _session.user_id)


@contracts_router.patch("/contract-folders/{folder_id}", status_code=status.HTTP_200_OK)
def update_folder(
    folder_id: str,
    payload: ContractFolderUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).update_folder(folder_id, payload, _session.user_id)


@contracts_router.delete("/contract-folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(
    folder_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete_folder(folder_id, _session.user_id)
    return None


# --- ContractFile ---

@contracts_router.get("/contract-files", status_code=status.HTTP_200_OK)
def get_files(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
    contract_id: int | None = Query(default=None),
    folder_id: str | None = Query(default=None),
):
    return build_service(supply_db).get_files(contract_id, folder_id)


@contracts_router.get("/contract-files/my", status_code=status.HTTP_200_OK)
def get_my_contract_files(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).get_my_files(_session.user_id)


@contracts_router.get("/contract-files/history", status_code=status.HTTP_200_OK)
def get_files_history(
    contract_id: int = Query(...),
    supply_db: DbSupplySession = None,
    _session=Depends(get_session),
):
    return build_service(supply_db).get_files_history(contract_id)


@contracts_router.get("/contract-files/{file_id}", status_code=status.HTTP_200_OK)
def get_file(
    file_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).get_file(file_id)


@contracts_router.post("/contract-files", status_code=status.HTTP_201_CREATED)
async def upload_files(
    files: Annotated[list[UploadFile], File(...)],
    supply_db: DbSupplySession,
    _session=Depends(get_session),
    contract_id: int = Form(...),
    contract_folder_id: str | None = Form(default=None),
    type: str | None = Form(default=None),
):
    service = build_service(supply_db)
    results = []
    for f in files:
        file_bytes = await f.read()
        results.append(service.upload(
            contract_id=contract_id,
            contract_folder_id=contract_folder_id,
            original_name=f.filename or "file",
            file_bytes=file_bytes,
            uploaded_by=_session.user_id,
            file_type=type,
        ))
    return results


@contracts_router.patch("/contract-files/{file_id}", status_code=status.HTTP_200_OK)
def update_file(
    file_id: str,
    payload: ContractFileUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).update_file(file_id, payload, _session.user_id)


@contracts_router.delete("/contract-files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(
    file_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete_file(file_id, _session.user_id)
    return None


@contracts_router.get("/contract-files/{file_id}/download", status_code=status.HTTP_200_OK)
def download_file(
    file_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    file_path, original_name = build_service(supply_db).get_download(file_id)
    return FileResponse(file_path, filename=original_name)


@contracts_router.get("/contract-files/{file_id}/preview", status_code=status.HTTP_200_OK)
def preview_file(
    file_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    file_path = build_service(supply_db).get_preview(file_id)
    return FileResponse(file_path, media_type="application/pdf")
