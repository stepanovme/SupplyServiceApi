from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.session import SessionDB
from app.models.supply_request import NomenclatureCompetitorCreate, NomenclatureCompetitorUpdate
from app.repositories.nomenclature_competitor_repository import NomenclatureCompetitorRepository
from app.services.nomenclature_competitor_service import NomenclatureCompetitorService

nomenclature_competitor_router = APIRouter(prefix="/nomenclature-competitors", tags=["Nomenclature Competitors"])


def build_service(db: DbSupplySession) -> NomenclatureCompetitorService:
    return NomenclatureCompetitorService(NomenclatureCompetitorRepository(db))


@nomenclature_competitor_router.get("")
def get_competitors_by_nomenclature(
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
    nomenclature_id: str = Query(...),
):
    return build_service(db).get_by_nomenclature(nomenclature_id)


@nomenclature_competitor_router.get("/{competitor_id}")
def get_competitor(
    competitor_id: str,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    result = build_service(db).get_by_id(competitor_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found")
    return result


@nomenclature_competitor_router.post("", status_code=status.HTTP_201_CREATED)
def create_competitor(
    payload: NomenclatureCompetitorCreate,
    db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    return build_service(db).create(payload, str(session.user_id))


@nomenclature_competitor_router.patch("/{competitor_id}")
def update_competitor(
    competitor_id: str,
    payload: NomenclatureCompetitorUpdate,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    result = build_service(db).update(competitor_id, payload)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found")
    return result


@nomenclature_competitor_router.delete("/{competitor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_competitor(
    competitor_id: str,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    deleted = build_service(db).delete(competitor_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found")
    return None


@nomenclature_competitor_router.get("/{competitor_id}/files")
def get_competitor_files(
    competitor_id: str,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    return build_service(db).get_files(competitor_id)


@nomenclature_competitor_router.post("/{competitor_id}/files", status_code=status.HTTP_201_CREATED)
async def upload_competitor_files(
    competitor_id: str,
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
                competitor_id=competitor_id,
                original_name=file.filename or "file",
                mime_type=file.content_type or "application/octet-stream",
                file_bytes=file_bytes,
                user_id=str(session.user_id),
            )
        )
    return results


@nomenclature_competitor_router.get("/{competitor_id}/files/{file_id}/download")
def download_competitor_file(
    competitor_id: str,
    file_id: str,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    payload = build_service(db).get_download_file_payload(competitor_id, file_id)
    return FileResponse(
        path=payload["path"],
        filename=payload["filename"],
        media_type=payload["media_type"],
    )


@nomenclature_competitor_router.get("/{competitor_id}/files/{file_id}/preview")
def preview_competitor_file(
    competitor_id: str,
    file_id: str,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    file_path = build_service(db).get_preview(file_id)
    return FileResponse(path=file_path, media_type="application/pdf")


@nomenclature_competitor_router.delete("/{competitor_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_competitor_file(
    competitor_id: str,
    file_id: str,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    build_service(db).delete_file(competitor_id, file_id)
    return None
