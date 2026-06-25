from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.database import DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.session import SessionDB
from app.models.warehouse_receipt import (
    WarehouseReceiptCreate,
    WarehouseReceiptItemCreate,
    WarehouseReceiptItemLogCreate,
    WarehouseReceiptItemLogUpdate,
    WarehouseReceiptItemUpdate,
    WarehouseReceiptLogCreate,
    WarehouseReceiptLogUpdate,
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
    warehouse_id: str | None = Query(default=None, description="Фильтр по складу"),
    _session=Depends(get_session),
):
    service = build_warehouse_receipt_service(supply_db, reference_db)
    return service.get_receipts(warehouse_id)


@warehouse_receipts_router.get(
    "/outgoing",
    status_code=status.HTTP_200_OK,
    summary="Получить список расходных накладных",
)
def get_outgoing_warehouse_receipts(
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_warehouse_receipt_service(supply_db, reference_db)
    return service.get_outgoing_receipts()


@warehouse_receipts_router.get(
    "/returns",
    status_code=status.HTTP_200_OK,
    summary="Получить список возвратных накладных",
)
def get_return_warehouse_receipts(
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_warehouse_receipt_service(supply_db, reference_db)
    return service.get_return_receipts()


@warehouse_receipts_router.get(
    "/inventory",
    status_code=status.HTTP_200_OK,
    summary="Получить список инвентаризационных накладных",
)
def get_inventory_warehouse_receipts(
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_warehouse_receipt_service(supply_db, reference_db)
    return service.get_inventory_receipts()


@warehouse_receipts_router.get(
    "/receipt-parties",
    status_code=status.HTTP_200_OK,
    summary="Получить уникальный список значений поля кому",
)
def get_warehouse_receipt_parties(
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_warehouse_receipt_service(supply_db, reference_db)
    return service.get_unique_receipt_parties()


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


@warehouse_receipts_router.post(
    "/outgoing",
    status_code=status.HTTP_201_CREATED,
    summary="Создать расходную накладную",
)
def create_outgoing_warehouse_receipt(
    payload: WarehouseReceiptCreate,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_warehouse_receipt_service(supply_db, reference_db)
    return service.create_outgoing_receipt(payload)


@warehouse_receipts_router.post(
    "/returns",
    status_code=status.HTTP_201_CREATED,
    summary="Создать возвратную накладную",
)
def create_return_warehouse_receipt(
    payload: WarehouseReceiptCreate,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_warehouse_receipt_service(supply_db, reference_db)
    return service.create_return_receipt(payload)


@warehouse_receipts_router.post(
    "/inventory",
    status_code=status.HTTP_201_CREATED,
    summary="Создать инвентаризационную накладную",
)
def create_inventory_warehouse_receipt(
    payload: WarehouseReceiptCreate,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_warehouse_receipt_service(supply_db, reference_db)
    return service.create_inventory_receipt(payload)


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


@warehouse_receipts_router.post(
    "/{receipt_id}/attachments",
    status_code=status.HTTP_201_CREATED,
    summary="Загрузить файлы к приходной накладной",
)
async def upload_warehouse_receipt_attachments(
    receipt_id: str,
    files: Annotated[list[UploadFile], File(...)],
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = build_warehouse_receipt_service(supply_db, reference_db)
    results = []
    for file in files or []:
        file_bytes = await file.read()
        results.append(
            service.upload_receipt_attachment(
                receipt_id=receipt_id,
                original_name=file.filename or "file",
                mime_type=file.content_type or "application/octet-stream",
                file_bytes=file_bytes,
                user_id=str(session.user_id),
            )
        )
    return results


@warehouse_receipts_router.get(
    "/{receipt_id}/attachments",
    status_code=status.HTTP_200_OK,
    summary="Получить список файлов приходной накладной",
)
def get_warehouse_receipt_attachments(
    receipt_id: str,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_warehouse_receipt_service(supply_db, reference_db)
    return service.get_receipt_files(receipt_id)


@warehouse_receipts_router.get(
    "/{receipt_id}/attachments/{file_id}/download",
    status_code=status.HTTP_200_OK,
    summary="Скачать файл приходной накладной",
)
def download_warehouse_receipt_attachment(
    receipt_id: str,
    file_id: str,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = build_warehouse_receipt_service(supply_db, reference_db)
    payload = service.get_download_file_payload(receipt_id, file_id, str(session.user_id))
    return FileResponse(
        path=payload["path"],
        filename=payload["filename"],
        media_type=payload["media_type"],
    )


@warehouse_receipts_router.delete(
    "/{receipt_id}/attachments/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить файл приходной накладной",
)
def delete_warehouse_receipt_attachment(
    receipt_id: str,
    file_id: str,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = build_warehouse_receipt_service(supply_db, reference_db)
    service.delete_receipt_file(receipt_id, file_id, str(session.user_id))
    return None


@warehouse_receipts_router.get(
    "/{receipt_id}/logs",
    status_code=status.HTTP_200_OK,
    summary="Получить логи накладной",
)
def get_warehouse_receipt_logs(
    receipt_id: str,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_warehouse_receipt_service(supply_db, reference_db)
    return service.get_receipt_logs(receipt_id)


@warehouse_receipts_router.post(
    "/{receipt_id}/logs",
    status_code=status.HTTP_201_CREATED,
    summary="Создать лог накладной",
)
def create_warehouse_receipt_log(
    receipt_id: str,
    payload: WarehouseReceiptLogCreate,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = build_warehouse_receipt_service(supply_db, reference_db)
    return service.create_receipt_log(receipt_id, payload, str(session.user_id))


@warehouse_receipts_router.patch(
    "/{receipt_id}/logs/{log_id}",
    status_code=status.HTTP_200_OK,
    summary="Изменить лог накладной",
)
def update_warehouse_receipt_log(
    receipt_id: str,
    log_id: int,
    payload: WarehouseReceiptLogUpdate,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_warehouse_receipt_service(supply_db, reference_db)
    return service.update_receipt_log(receipt_id, log_id, payload)


@warehouse_receipts_router.delete(
    "/{receipt_id}/logs/{log_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить лог накладной",
)
def delete_warehouse_receipt_log(
    receipt_id: str,
    log_id: int,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_warehouse_receipt_service(supply_db, reference_db)
    service.delete_receipt_log(receipt_id, log_id)
    return None


@warehouse_receipts_router.get(
    "/{receipt_id}/items/{item_id}/logs",
    status_code=status.HTTP_200_OK,
    summary="Получить логи позиции накладной",
)
def get_warehouse_receipt_item_logs(
    receipt_id: str,
    item_id: str,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_warehouse_receipt_service(supply_db, reference_db)
    return service.get_receipt_item_logs(receipt_id, item_id)


@warehouse_receipts_router.post(
    "/{receipt_id}/items/{item_id}/logs",
    status_code=status.HTTP_201_CREATED,
    summary="Создать лог позиции накладной",
)
def create_warehouse_receipt_item_log(
    receipt_id: str,
    item_id: str,
    payload: WarehouseReceiptItemLogCreate,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = build_warehouse_receipt_service(supply_db, reference_db)
    return service.create_receipt_item_log(receipt_id, item_id, payload, str(session.user_id))


@warehouse_receipts_router.patch(
    "/{receipt_id}/items/{item_id}/logs/{log_id}",
    status_code=status.HTTP_200_OK,
    summary="Изменить лог позиции накладной",
)
def update_warehouse_receipt_item_log(
    receipt_id: str,
    item_id: str,
    log_id: int,
    payload: WarehouseReceiptItemLogUpdate,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_warehouse_receipt_service(supply_db, reference_db)
    return service.update_receipt_item_log(receipt_id, item_id, log_id, payload)


@warehouse_receipts_router.delete(
    "/{receipt_id}/items/{item_id}/logs/{log_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить лог позиции накладной",
)
def delete_warehouse_receipt_item_log(
    receipt_id: str,
    item_id: str,
    log_id: int,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_warehouse_receipt_service(supply_db, reference_db)
    service.delete_receipt_item_log(receipt_id, item_id, log_id)
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
