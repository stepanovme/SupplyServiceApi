from fastapi import APIRouter, Depends, status

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.supply_request import RequestItemCreate, RequestItemUpdate
from app.repositories.request_repository import RequestRepository
from app.services.request_item_service import RequestItemService

request_items_router = APIRouter(prefix="/requests", tags=["RequestItems"])


@request_items_router.post(
    "/{request_id}/items",
    status_code=status.HTTP_201_CREATED,
    summary="Добавить предмет в заявку",
)
def create_request_item(
    request_id: int,
    payload: RequestItemCreate,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = RequestItemService(RequestRepository(db))
    return service.create(request_id, payload)


@request_items_router.patch(
    "/{request_id}/items/{item_id}",
    status_code=status.HTTP_200_OK,
    summary="Редактировать предмет в заявке",
)
def update_request_item(
    request_id: int,
    item_id: str,
    payload: RequestItemUpdate,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = RequestItemService(RequestRepository(db))
    return service.update(request_id, item_id, payload)
