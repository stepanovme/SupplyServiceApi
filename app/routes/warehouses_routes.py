from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.database import DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.session import SessionDB
from app.models.warehouse import (
    WarehouseCreate,
    WarehouseListCreate,
    WarehouseListUpdate,
    WarehouseTransferCancelRequest,
    WarehouseTransferRequest,
    WarehouseUpdate,
)
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.repositories.warehouse_receipt_repository import WarehouseReceiptRepository
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
    session=Depends(get_session),
):
    service = WarehouseService(WarehouseRepository(db))
    return service.create(payload, str(session.user_id))


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


@warehouses_router.post(
    "/transfer",
    status_code=status.HTTP_200_OK,
    summary="Переместить номенклатуру между складами",
)
def transfer_warehouse_items(
    payload: WarehouseTransferRequest,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = WarehouseService(WarehouseRepository(db))
    return service.transfer_items(payload)


@warehouses_router.post(
    "/transfer/cancel",
    status_code=status.HTTP_200_OK,
    summary="Отменить перемещение номенклатуры",
)
def cancel_warehouse_transfer(
    payload: WarehouseTransferCancelRequest,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    receipt_repo = WarehouseReceiptRepository(supply_db)
    receipt = receipt_repo.get_receipt_by_id(payload.warehouse_receipt_id)
    if not receipt or receipt.type != 5:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer receipt not found")

    items = receipt_repo.get_receipt_items(receipt.id)
    if not items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Receipt has no items")

    service = WarehouseService(WarehouseRepository(supply_db))
    return service.cancel_transfer(receipt, items)


@warehouses_router.get(
    "/{warehouse_id}/list",
    status_code=status.HTTP_200_OK,
    summary="Получить список номенклатуры на складе",
)
def get_warehouse_list(
    warehouse_id: str,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = WarehouseService(
        WarehouseRepository(supply_db),
        ReferenceObjectRepository(reference_db),
    )
    return service.get_warehouse_list(warehouse_id, user_id=str(session.user_id))


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
