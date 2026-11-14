from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.database import DbAuthSession, DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.documents_list import DocumentsListAttach, DocumentsListCreate, DocumentsListUpdate
from app.repositories.act_repository import ActRepository
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.contract_repository import ContractRepository
from app.repositories.department_repository import DepartmentRepository
from app.repositories.document_access_setting_repository import DocumentAccessSettingRepository
from app.repositories.documents_list_repository import DocumentsListRepository
from app.repositories.letter_repository import LetterRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.services.document_access_setting_service import DocumentAccessSettingService
from app.services.documents_list_service import DocumentsListService

documents_list_router = APIRouter(prefix="/documents-list", tags=["DocumentsList"])


def build_service(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession | None = None,
    reference_db: DbReferenceSession | None = None,
) -> DocumentsListService:
    return DocumentsListService(
        DocumentsListRepository(supply_db),
        AuthUserRepository(auth_db) if auth_db else None,
        ReferenceObjectRepository(reference_db) if reference_db else None,
        contract_repo=ContractRepository(supply_db),
        act_repo=ActRepository(supply_db),
        letter_repo=LetterRepository(supply_db),
        department_repo=DepartmentRepository(supply_db),
        doc_access_service=DocumentAccessSettingService(DocumentAccessSettingRepository(supply_db)),
    )


@documents_list_router.get("/my", status_code=status.HTTP_200_OK)
def get_my_documents(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
    unattached_only: bool = Query(default=False),
):
    return build_service(supply_db, auth_db, reference_db).get_my(_session.user_id, unattached_only)


@documents_list_router.get("", status_code=status.HTTP_200_OK)
def get_documents(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
    unattached_only: bool = Query(default=False),
):
    return build_service(supply_db, auth_db, reference_db).get_all(unattached_only)


@documents_list_router.get("/{document_id}", status_code=status.HTTP_200_OK)
def get_document(
    document_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_by_id(document_id)


@documents_list_router.get("/{document_id}/access", status_code=status.HTTP_200_OK)
def check_document_access(
    document_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_service(supply_db, auth_db, reference_db)
    doc = service.repo.get_by_id(document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    dept_repo = service.department_repo
    doc_access = service.doc_access_service
    dept_ids = dept_repo.get_department_ids_for_user(str(_session.user_id)) if dept_repo else []
    counterparty_ids = [doc.from_whom_id] if doc.from_whom_id else []
    return doc_access.check_document_access(
        "document", str(_session.user_id), dept_ids, counterparty_ids,
    )


@documents_list_router.get("/{document_id}/download", status_code=status.HTTP_200_OK)
def download_document(
    document_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    file_path, original_name = build_service(supply_db).get_download(document_id)
    return FileResponse(file_path, filename=original_name)


@documents_list_router.get("/{document_id}/preview", status_code=status.HTTP_200_OK)
def preview_document(
    document_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    file_path = build_service(supply_db).get_preview(document_id)
    return FileResponse(file_path, media_type="application/pdf")


@documents_list_router.post("", status_code=status.HTTP_201_CREATED)
def upload_document(
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
    type: str | None = Form(default=None),
    document_id: str | None = Form(default=None),
    document_type: str | None = Form(default=None),
    from_whom_id: str | None = Form(default=None),
    object_id: str | None = Form(default=None),
    object_type: str | None = Form(default=None),
    customer_id: str | None = Form(default=None),
    contractor_id: str | None = Form(default=None),
    files: list[UploadFile] = File(...),
):
    service = build_service(supply_db, reference_db=reference_db)

    payload = None
    if type is not None or document_id is not None or document_type is not None or from_whom_id is not None or object_id is not None or object_type is not None or customer_id is not None or contractor_id is not None:
        payload = DocumentsListCreate(
            type=type,
            document_id=document_id,
            document_type=document_type,
            from_whom_id=from_whom_id,
            object_id=object_id,
            object_type=object_type,
            customer_id=customer_id,
            contractor_id=contractor_id,
        )

    results = []
    for f in files:
        results.append(service.upload_file(f, _session.user_id, payload))
    return results


@documents_list_router.patch("/{document_id}", status_code=status.HTTP_200_OK)
def update_document(
    document_id: int,
    payload: DocumentsListUpdate,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, reference_db=reference_db).update(document_id, payload, _session.user_id)


@documents_list_router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete(document_id)
    return None


@documents_list_router.post("/{document_id}/attach/contract", status_code=status.HTTP_201_CREATED)
def attach_to_contract(
    document_id: int,
    payload: DocumentsListAttach,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    if payload.contract_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="contract_id is required")
    return build_service(supply_db).attach_to_contract(
        document_id,
        payload.contract_id,
        _session.user_id,
        contract_folder_id=payload.contract_folder_id,
        file_type=payload.type,
    )


@documents_list_router.post("/{document_id}/attach/act", status_code=status.HTTP_201_CREATED)
def attach_to_act(
    document_id: int,
    payload: DocumentsListAttach,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    if payload.act_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="act_id is required")
    return build_service(supply_db).attach_to_act(
        document_id,
        payload.act_id,
        _session.user_id,
        act_folder_id=payload.act_folder_id,
        file_type=payload.type,
    )


@documents_list_router.post("/{document_id}/attach/letter", status_code=status.HTTP_201_CREATED)
def attach_to_letter(
    document_id: int,
    payload: DocumentsListAttach,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    if payload.letter_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="letter_id is required")
    return build_service(supply_db).attach_to_letter(
        document_id,
        payload.letter_id,
        _session.user_id,
        letter_folder_id=payload.letter_folder_id,
        file_type=payload.type,
    )