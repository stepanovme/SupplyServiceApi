from fastapi import APIRouter, Depends, status

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.request_warehouse_list import RequestWarehouseListCreate, RequestWarehouseListUpdate
from app.models.session import SessionDB
from app.repositories.request_warehouse_list_repository import RequestWarehouseListRepository
from app.services.request_warehouse_list_service import RequestWarehouseListService

request_warehouse_lists_router = APIRouter(prefix="/request-warehouse-lists", tags=["RequestWarehouseLists"])


def build_service(db: DbSupplySession) -> RequestWarehouseListService:
    return RequestWarehouseListService(RequestWarehouseListRepository(db))


@request_warehouse_lists_router.get("", status_code=status.HTTP_200_OK)
def get_request_warehouse_lists(db: DbSupplySession, _session=Depends(get_session)):
    return build_service(db).get_all()


@request_warehouse_lists_router.get("/{row_id}", status_code=status.HTTP_200_OK)
def get_request_warehouse_list(row_id: str, db: DbSupplySession, _session=Depends(get_session)):
    return build_service(db).get_by_id(row_id)


@request_warehouse_lists_router.post("", status_code=status.HTTP_201_CREATED)
def create_request_warehouse_list(
    payload: RequestWarehouseListCreate,
    db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    return build_service(db).create(payload, str(session.user_id))


@request_warehouse_lists_router.patch("/{row_id}", status_code=status.HTTP_200_OK)
def update_request_warehouse_list(
    row_id: str,
    payload: RequestWarehouseListUpdate,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(db).update(row_id, payload)


@request_warehouse_lists_router.delete("/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_request_warehouse_list(row_id: str, db: DbSupplySession, _session=Depends(get_session)):
    build_service(db).delete(row_id)
    return None
