from fastapi import APIRouter, Depends, status

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.supply_request import RequestApproverCreate, RequestApproverUpdate
from app.repositories.request_repository import RequestRepository
from app.services.request_approver_service import RequestApproverService

request_approvers_router = APIRouter(prefix="/requests", tags=["RequestApprovers"])


@request_approvers_router.post(
    "/{request_id}/approvers",
    status_code=status.HTTP_201_CREATED,
    summary="Добавить согласующего в заявку",
)
def create_request_approver(
    request_id: int,
    payload: RequestApproverCreate,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = RequestApproverService(RequestRepository(db))
    return service.create(request_id, payload)


@request_approvers_router.patch(
    "/{request_id}/approvers/{log_id}",
    status_code=status.HTTP_200_OK,
    summary="Редактировать согласующего в заявке",
)
def update_request_approver(
    request_id: int,
    log_id: str,
    payload: RequestApproverUpdate,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = RequestApproverService(RequestRepository(db))
    return service.update(request_id, log_id, payload)


@request_approvers_router.delete(
    "/{request_id}/approvers/{log_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить согласующего из заявки",
)
def delete_request_approver(
    request_id: int,
    log_id: str,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = RequestApproverService(RequestRepository(db))
    service.delete(request_id, log_id)
    return None
