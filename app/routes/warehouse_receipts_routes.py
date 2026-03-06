from fastapi import APIRouter, Depends, status

from app.database import DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.warehouse_receipt import (
    WarehouseReceiptCreate,
    WarehouseReceiptItemCreate,
    WarehouseReceiptItemUpdate,
    WarehouseReceiptUpdate,
)
from app.repositories.counterparty_repository import CounterpartyRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.repositories.warehouse_receipt_repository import WarehouseReceiptRepository
from app.services.warehouse_receipt_service import WarehouseReceiptService

warehouse_receipts_router = APIRouter(prefix="/warehouse-receipts", tags=["WarehouseReceipts"])


def build_warehouse_receipt_service(
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
) -> WarehouseReceiptService:
    return WarehouseReceiptService(
        WarehouseReceiptRepository(supply_db),
        CounterpartyRepository(reference_db),
        ReferenceObjectRepository(reference_db),
    )


@warehouse_receipts_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Получить список приходных накладных",
)
def get_warehouse_receipts(
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_warehouse_receipt_service(supply_db, reference_db)
    return service.get_receipts()


@warehouse_receipts_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать приходную накладную",
)
def create_warehouse_receipt(
    payload: WarehouseReceiptCreate,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_warehouse_receipt_service(supply_db, reference_db)
    return service.create_receipt(payload)


@warehouse_receipts_router.get(
    "/{receipt_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить приходную накладную",
)
def get_warehouse_receipt(
    receipt_id: str,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_warehouse_receipt_service(supply_db, reference_db)
    return service.get_receipt(receipt_id)


@warehouse_receipts_router.patch(
    "/{receipt_id}",
    status_code=status.HTTP_200_OK,
    summary="Изменить приходную накладную",
)
def update_warehouse_receipt(
    receipt_id: str,
    payload: WarehouseReceiptUpdate,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_warehouse_receipt_service(supply_db, reference_db)
    return service.update_receipt(receipt_id, payload)


@warehouse_receipts_router.delete(
    "/{receipt_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить приходную накладную",
)
def delete_warehouse_receipt(
    receipt_id: str,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_warehouse_receipt_service(supply_db, reference_db)
    service.delete_receipt(receipt_id)
    return None


@warehouse_receipts_router.get(
    "/{receipt_id}/items",
    status_code=status.HTTP_200_OK,
    summary="Получить позиции приходной накладной",
)
def get_warehouse_receipt_items(
    receipt_id: str,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_warehouse_receipt_service(supply_db, reference_db)
    return service.get_receipt_items(receipt_id)


@warehouse_receipts_router.post(
    "/{receipt_id}/items",
    status_code=status.HTTP_201_CREATED,
    summary="Создать позицию приходной накладной",
)
def create_warehouse_receipt_item(
    receipt_id: str,
    payload: WarehouseReceiptItemCreate,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_warehouse_receipt_service(supply_db, reference_db)
    return service.create_receipt_item(receipt_id, payload)


@warehouse_receipts_router.patch(
    "/{receipt_id}/items/{item_id}",
    status_code=status.HTTP_200_OK,
    summary="Изменить позицию приходной накладной",
)
def update_warehouse_receipt_item(
    receipt_id: str,
    item_id: str,
    payload: WarehouseReceiptItemUpdate,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_warehouse_receipt_service(supply_db, reference_db)
    return service.update_receipt_item(receipt_id, item_id, payload)


@warehouse_receipts_router.delete(
    "/{receipt_id}/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить позицию приходной накладной",
)
def delete_warehouse_receipt_item(
    receipt_id: str,
    item_id: str,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_warehouse_receipt_service(supply_db, reference_db)
    service.delete_receipt_item(receipt_id, item_id)
    return None
