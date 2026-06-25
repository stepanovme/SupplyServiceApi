from fastapi import APIRouter, Depends, Query, status

from app.database import DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.warehouse import (
    WarehouseCreate,
    WarehouseListCreate,
    WarehouseListUpdate,
    WarehouseUpdate,
)
from app.repositories.reference_object_repository import ReferenceObjectRepository
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


@warehouses_router.get(
    "/{warehouse_id}/list",
    status_code=status.HTTP_200_OK,
    summary="Получить список номенклатуры на складе",
)
def get_warehouse_list(
    warehouse_id: str,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = WarehouseService(
        WarehouseRepository(supply_db),
        ReferenceObjectRepository(reference_db),
    )
    return service.get_warehouse_list(warehouse_id)


@warehouses_router.get(
    "/list/all",
    status_code=status.HTTP_200_OK,
    summary="Получить список номенклатуры по всем складам",
)
def get_all_warehouses_list(
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    search: str | None = Query(default=None, description="Поиск по наименованию номенклатуры"),
    _session=Depends(get_session),
):
    service = WarehouseService(
        WarehouseRepository(supply_db),
        ReferenceObjectRepository(reference_db),
    )
    return service.get_all_warehouse_list(search)


@warehouses_router.post(
    "/{warehouse_id}/list",
    status_code=status.HTTP_201_CREATED,
    summary="Создать строку списка склада",
)
def create_warehouse_list_row(
    warehouse_id: str,
    payload: WarehouseListCreate,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = WarehouseService(
        WarehouseRepository(supply_db),
        ReferenceObjectRepository(reference_db),
    )
    return service.create_warehouse_list_row(warehouse_id, payload)


@warehouses_router.delete(
    "/{warehouse_id}/list/{row_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить строку списка склада",
)
def delete_warehouse_list_row(
    warehouse_id: str,
    row_id: str,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = WarehouseService(
        WarehouseRepository(supply_db),
        ReferenceObjectRepository(reference_db),
    )
    service.delete_warehouse_list_row(warehouse_id, row_id)
    return None


@warehouses_router.patch(
    "/{warehouse_id}/list/{row_id}",
    status_code=status.HTTP_200_OK,
    summary="Изменить строку списка склада",
)
def update_warehouse_list_row(
    warehouse_id: str,
    row_id: str,
    payload: WarehouseListUpdate,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = WarehouseService(
        WarehouseRepository(supply_db),
        ReferenceObjectRepository(reference_db),
    )
    return service.update_warehouse_list_row(warehouse_id, row_id, payload)
