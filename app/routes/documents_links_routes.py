from fastapi import APIRouter, Depends, Query, status

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.documents_link import DocumentsLinkCreate, DocumentsLinkUpdate
from app.repositories.documents_link_repository import DocumentsLinkRepository
from app.services.documents_link_service import DocumentsLinkService

documents_links_router = APIRouter(prefix="/documents-links", tags=["Documents Links"])


def build_service(db: DbSupplySession) -> DocumentsLinkService:
    return DocumentsLinkService(DocumentsLinkRepository(db))


@documents_links_router.get("", status_code=status.HTTP_200_OK)
def get_all(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
    document_linked_first: str | None = Query(default=None),
    document_type_first: str | None = Query(default=None),
    document_linked_second: str | None = Query(default=None),
    document_type_second: str | None = Query(default=None),
):
    return build_service(supply_db).get_all(
        document_linked_first, document_type_first,
        document_linked_second, document_type_second,
    )


@documents_links_router.get("/by-document/{document_id}", status_code=status.HTTP_200_OK)
def get_by_document(
    document_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).get_by_document(document_id)


@documents_links_router.get("/{link_id}", status_code=status.HTTP_200_OK)
def get_by_id(
    link_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).get_by_id(link_id)


@documents_links_router.post("", status_code=status.HTTP_201_CREATED)
def create(
    payload: DocumentsLinkCreate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).create(payload, _session.user_id)


@documents_links_router.patch("/{link_id}", status_code=status.HTTP_200_OK)
def update(
    link_id: str,
    payload: DocumentsLinkUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).update(link_id, payload)


@documents_links_router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    link_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete(link_id)
    return None
