from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.database import DbAuthSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.session import SessionDB
from app.models.supply_request import NomenclatureFeedbackCreate, NomenclatureFeedbackUpdate
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.nomenclature_feedback_repository import NomenclatureFeedbackRepository
from app.services.nomenclature_feedback_service import NomenclatureFeedbackService

nomenclature_feedback_router = APIRouter(prefix="/nomenclature-feedback", tags=["Nomenclature Feedback"])


def build_service(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession | None = None,
) -> NomenclatureFeedbackService:
    return NomenclatureFeedbackService(
        NomenclatureFeedbackRepository(supply_db),
        AuthUserRepository(auth_db) if auth_db else None,
    )


@nomenclature_feedback_router.get("")
def get_feedback_by_nomenclature(
    db: DbSupplySession,
    auth_db: DbAuthSession,
    _session: SessionDB = Depends(get_session),
    nomenclature_id: str = Query(...),
):
    return build_service(db, auth_db).get_by_nomenclature(nomenclature_id)


@nomenclature_feedback_router.get("/{feedback_id}")
def get_feedback(
    feedback_id: str,
    db: DbSupplySession,
    auth_db: DbAuthSession,
    _session: SessionDB = Depends(get_session),
):
    result = build_service(db, auth_db).get_by_id(feedback_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")
    return result


@nomenclature_feedback_router.post("", status_code=status.HTTP_201_CREATED)
def create_feedback(
    payload: NomenclatureFeedbackCreate,
    db: DbSupplySession,
    auth_db: DbAuthSession,
    session: SessionDB = Depends(get_session),
):
    return build_service(db, auth_db).create(payload, str(session.user_id))


@nomenclature_feedback_router.patch("/{feedback_id}")
def update_feedback(
    feedback_id: str,
    payload: NomenclatureFeedbackUpdate,
    db: DbSupplySession,
    auth_db: DbAuthSession,
    _session: SessionDB = Depends(get_session),
):
    result = build_service(db, auth_db).update(feedback_id, payload)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")
    return result


@nomenclature_feedback_router.delete("/{feedback_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_feedback(
    feedback_id: str,
    db: DbSupplySession,
    auth_db: DbAuthSession,
    _session: SessionDB = Depends(get_session),
):
    deleted = build_service(db, auth_db).delete(feedback_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")
    return None


@nomenclature_feedback_router.get("/{feedback_id}/files")
def get_feedback_files(
    feedback_id: str,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    return build_service(db).get_files(feedback_id)


@nomenclature_feedback_router.post("/{feedback_id}/files", status_code=status.HTTP_201_CREATED)
async def upload_feedback_files(
    feedback_id: str,
    files: Annotated[list[UploadFile], File(...)],
    db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    service = build_service(db)
    results = []
    for file in files or []:
        file_bytes = await file.read()
        results.append(
            service.upload_file(
                feedback_id=feedback_id,
                original_name=file.filename or "file",
                file_bytes=file_bytes,
                user_id=str(session.user_id),
            )
        )
    return results


@nomenclature_feedback_router.get("/{feedback_id}/files/{file_id}/download")
def download_feedback_file(
    feedback_id: str,
    file_id: str,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    payload = build_service(db).get_download_file_payload(feedback_id, file_id)
    return FileResponse(
        path=payload["path"],
        filename=payload["filename"],
        media_type=payload["media_type"],
    )


@nomenclature_feedback_router.get("/{feedback_id}/files/{file_id}/preview")
def preview_feedback_file(
    feedback_id: str,
    file_id: str,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    file_path = build_service(db).get_preview(file_id)
    return FileResponse(path=file_path, media_type="application/pdf")


@nomenclature_feedback_router.delete("/{feedback_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_feedback_file(
    feedback_id: str,
    file_id: str,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    build_service(db).delete_file(feedback_id, file_id)
    return None
