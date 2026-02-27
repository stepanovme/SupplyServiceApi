from fastapi import APIRouter, Depends, HTTPException, status

from app.database import DbAuthSession, DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.session import SessionDB
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.repositories.request_repository import RequestRepository
from app.services.request_service import RequestService

requests_router = APIRouter(prefix="/requests", tags=["Requests"])


@requests_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Получить список всех заявок",
)
def get_all_requests(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = RequestService(
        RequestRepository(supply_db),
        AuthUserRepository(auth_db),
        ReferenceObjectRepository(reference_db),
    )
    return service.get_all()


@requests_router.get(
    "/my",
    status_code=status.HTTP_200_OK,
    summary="Получить список доступных мне заявок",
)
def get_my_requests(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = RequestService(
        RequestRepository(supply_db),
        AuthUserRepository(auth_db),
        ReferenceObjectRepository(reference_db),
    )
    return service.get_available_for_user(str(session.user_id))


@requests_router.get(
    "/my/{request_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить доступную мне заявку по id",
)
def get_my_request_by_id(
    request_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = RequestService(
        RequestRepository(supply_db),
        AuthUserRepository(auth_db),
        ReferenceObjectRepository(reference_db),
    )
    item = service.get_available_for_user_by_id(str(session.user_id), request_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return item


@requests_router.get(
    "/{request_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить заявку по id",
)
def get_request_by_id(
    request_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = RequestService(
        RequestRepository(supply_db),
        AuthUserRepository(auth_db),
        ReferenceObjectRepository(reference_db),
    )
    item = service.get_by_id(request_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return item
