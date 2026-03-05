from fastapi import APIRouter, Depends, status

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.warehouse import WarehouseCreate, WarehouseUpdate
from app.repositories.warehouse_repository import WarehouseRepository
from app.services.warehouse_service import WarehouseService

warehouses_router = APIRouter(prefix="/warehouses", tags=["Warehouses"])


@warehouses_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Получить список складов",
)
def get_warehouses(
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = WarehouseService(WarehouseRepository(db))
    return service.get_all()


@warehouses_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать склад",
)
def create_warehouse(
    payload: WarehouseCreate,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = WarehouseService(WarehouseRepository(db))
    return service.create(payload)


@warehouses_router.patch(
    "/{warehouse_id}",
    status_code=status.HTTP_200_OK,
    summary="Обновить склад",
)
def update_warehouse(
    warehouse_id: str,
    payload: WarehouseUpdate,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = WarehouseService(WarehouseRepository(db))
    return service.update(warehouse_id, payload)


@warehouses_router.delete(
    "/{warehouse_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить склад",
)
def delete_warehouse(
    warehouse_id: str,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = WarehouseService(WarehouseRepository(db))
    return service.delete(warehouse_id)
