from fastapi import APIRouter, Depends, status

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.request_specification import RequestSpecificationCreate, RequestSpecificationUpdate
from app.models.session import SessionDB
from app.repositories.request_specification_repository import RequestSpecificationRepository
from app.services.request_specification_service import RequestSpecificationService

request_specifications_router = APIRouter(prefix="/request-specifications", tags=["RequestSpecifications"])


def build_service(db: DbSupplySession) -> RequestSpecificationService:
    return RequestSpecificationService(RequestSpecificationRepository(db))


@request_specifications_router.get("", status_code=status.HTTP_200_OK)
def get_request_specifications(
    request_id: int | None = None,
    specification_id: str | None = None,
    db: DbSupplySession = None,
    _session=Depends(get_session),
):
    service = build_service(db)
    if request_id is not None:
        return service.get_by_request_id(request_id)
    if specification_id is not None:
        return service.get_by_specification_id(specification_id)
    return service.get_all()


@request_specifications_router.get("/{row_id}", status_code=status.HTTP_200_OK)
def get_request_specification(row_id: str, db: DbSupplySession, _session=Depends(get_session)):
    return build_service(db).get_by_id(row_id)


@request_specifications_router.post("", status_code=status.HTTP_201_CREATED)
def create_request_specification(
    payload: RequestSpecificationCreate,
    db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    return build_service(db).create(payload, str(session.user_id))


@request_specifications_router.patch("/{row_id}", status_code=status.HTTP_200_OK)
def update_request_specification(
    row_id: str,
    payload: RequestSpecificationUpdate,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(db).update(row_id, payload)


@request_specifications_router.delete("/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_request_specification(row_id: str, db: DbSupplySession, _session=Depends(get_session)):
    build_service(db).delete(row_id)
    return None
