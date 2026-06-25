from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.session import SessionDB
from app.models.supply_request import (
    NomenclatureCreate,
    NomenclatureUpdate,
    UnitCreate,
    WarehousePriceHistoryCreate,
    WarehousePriceHistoryUpdate,
    WarehouseCategoryCreate,
    WarehouseCategoryUpdate,
)
from app.repositories.catalog_repository import CatalogRepository
from app.repositories.request_repository import RequestRepository
from app.repositories.request_file_repository import RequestFileRepository
from app.services.catalog_service import CatalogService
from app.services.request_file_service import RequestFileService

catalog_router = APIRouter(tags=["Catalog"])


@catalog_router.get(
    "/units",
    status_code=status.HTTP_200_OK,
    summary="Получить список единиц измерения",
)
def get_units(
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = CatalogService(CatalogRepository(db), RequestRepository(db))
    return service.get_units()


@catalog_router.post(
    "/units",
    status_code=status.HTTP_201_CREATED,
    summary="Создать единицу измерения",
)
def create_unit(
    payload: UnitCreate,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = CatalogService(CatalogRepository(db), RequestRepository(db))
    return service.create_unit(payload)


@catalog_router.get(
    "/warehouse-categories",
    status_code=status.HTTP_200_OK,
    summary="Получить список товарных категорий",
)
def get_warehouse_categories(
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = CatalogService(CatalogRepository(db), RequestRepository(db))
    return service.get_warehouse_categories()


@catalog_router.post(
    "/warehouse-categories",
    status_code=status.HTTP_201_CREATED,
    summary="Создать товарную категорию",
)
def create_warehouse_category(
    payload: WarehouseCategoryCreate,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = CatalogService(CatalogRepository(db), RequestRepository(db))
    return service.create_warehouse_category(payload)


@catalog_router.patch(
    "/warehouse-categories/{category_id}",
    status_code=status.HTTP_200_OK,
    summary="Обновить товарную категорию",
)
def update_warehouse_category(
    category_id: str,
    payload: WarehouseCategoryUpdate,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = CatalogService(CatalogRepository(db), RequestRepository(db))
    return service.update_warehouse_category(category_id, payload)


@catalog_router.get(
    "/nomenclature",
    status_code=status.HTTP_200_OK,
    summary="Получить список номенклатуры",
)
def get_nomenclature(
    db: DbSupplySession,
    search: str | None = Query(default=None, description="Поиск по совпадению в имени"),
    _session=Depends(get_session),
):
    service = CatalogService(CatalogRepository(db), RequestRepository(db))
    return service.get_nomenclature(search)


@catalog_router.get(
    "/nomenclature/{nomenclature_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить номенклатуру по id",
)
def get_nomenclature_by_id(
    nomenclature_id: str,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = CatalogService(CatalogRepository(db), RequestRepository(db))
    return service.get_nomenclature_by_id(nomenclature_id)


@catalog_router.get(
    "/nomenclature/{nomenclature_id}/receipt-history",
    status_code=status.HTTP_200_OK,
    summary="Получить историю поступления номенклатуры",
)
def get_nomenclature_receipt_history(
    nomenclature_id: str,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = CatalogService(CatalogRepository(db), RequestRepository(db))
    return service.get_nomenclature_receipt_history(nomenclature_id)


@catalog_router.get(
    "/nomenclature/{nomenclature_id}/movement-history",
    status_code=status.HTTP_200_OK,
    summary="Получить историю движения номенклатуры",
)
def get_nomenclature_movement_history(
    nomenclature_id: str,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = CatalogService(CatalogRepository(db), RequestRepository(db))
    return service.get_nomenclature_movement_history(nomenclature_id)


@catalog_router.get(
    "/nomenclature/{nomenclature_id}/purchase-price-stats",
    status_code=status.HTTP_200_OK,
    summary="Получить сводку закупочных цен номенклатуры",
)
def get_nomenclature_purchase_price_stats(
    nomenclature_id: str,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = CatalogService(CatalogRepository(db), RequestRepository(db))
    return service.get_nomenclature_purchase_price_stats(nomenclature_id)


@catalog_router.post(
    "/nomenclature",
    status_code=status.HTTP_201_CREATED,
    summary="Создать номенклатуру",
)
def create_nomenclature(
    payload: NomenclatureCreate,
    db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    service = CatalogService(CatalogRepository(db), RequestRepository(db))
    return service.create_nomenclature(payload, str(session.user_id))


@catalog_router.patch(
    "/nomenclature/{nomenclature_id}",
    status_code=status.HTTP_200_OK,
    summary="Обновить номенклатуру",
)
def update_nomenclature(
    nomenclature_id: str,
    payload: NomenclatureUpdate,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = CatalogService(CatalogRepository(db), RequestRepository(db))
    return service.update_nomenclature(nomenclature_id, payload)


@catalog_router.delete(
    "/nomenclature/{nomenclature_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить номенклатуру",
)
def delete_nomenclature(
    nomenclature_id: str,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = CatalogService(CatalogRepository(db), RequestRepository(db))
    return service.delete_nomenclature(nomenclature_id)


@catalog_router.post(
    "/nomenclature/{nomenclature_id}/photos",
    status_code=status.HTTP_201_CREATED,
    summary="Загрузить фотографии номенклатуры",
)
async def upload_nomenclature_photos(
    nomenclature_id: str,
    files: Annotated[list[UploadFile], File(...)],
    db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    service = RequestFileService(RequestFileRepository(db))
    results = []
    for file in files:
        file_bytes = await file.read()
        results.append(
            service.upload_nomenclature_photo(
                nomenclature_id=nomenclature_id,
                original_name=file.filename or "file",
                mime_type=file.content_type or "application/octet-stream",
                file_bytes=file_bytes,
                user_id=str(session.user_id),
            )
        )
    return results


@catalog_router.get(
    "/nomenclature/{nomenclature_id}/photos",
    status_code=status.HTTP_200_OK,
    summary="Получить список фотографий номенклатуры",
)
def get_nomenclature_photos(
    nomenclature_id: str,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = RequestFileService(RequestFileRepository(db))
    return service.get_nomenclature_photos(nomenclature_id)


@catalog_router.get(
    "/nomenclature/{nomenclature_id}/photos/{file_id}/download",
    status_code=status.HTTP_200_OK,
    summary="Скачать фотографию номенклатуры",
)
def download_nomenclature_photo(
    nomenclature_id: str,
    file_id: str,
    db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    service = RequestFileService(RequestFileRepository(db))
    payload = service.get_nomenclature_download_file_payload(
        nomenclature_id,
        file_id,
        str(session.user_id),
    )
    return FileResponse(
        path=payload["path"],
        filename=payload["filename"],
        media_type=payload["media_type"],
    )


@catalog_router.delete(
    "/nomenclature/{nomenclature_id}/photos/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить фотографию номенклатуры",
)
def delete_nomenclature_photo(
    nomenclature_id: str,
    file_id: str,
    db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    service = RequestFileService(RequestFileRepository(db))
    service.delete_nomenclature_photo(nomenclature_id, file_id, str(session.user_id))
    return None


@catalog_router.get(
    "/nomenclature/{nomenclature_id}/price-history",
    status_code=status.HTTP_200_OK,
    summary="Получить историю цен номенклатуры",
)
def get_nomenclature_price_history(
    nomenclature_id: str,
    db: DbSupplySession,
    price_type: str | None = Query(default=None, alias="type", description="Фильтр по типу цены"),
    _session=Depends(get_session),
):
    service = CatalogService(CatalogRepository(db), RequestRepository(db))
    return service.get_price_history(nomenclature_id, price_type)


@catalog_router.get(
    "/warehouse-price-history",
    status_code=status.HTTP_200_OK,
    summary="Получить историю цен",
)
def get_warehouse_price_history(
    nomenclature_id: str,
    db: DbSupplySession,
    price_type: str | None = Query(default=None, alias="type", description="Фильтр по типу цены"),
    _session=Depends(get_session),
):
    service = CatalogService(CatalogRepository(db), RequestRepository(db))
    return service.get_price_history(nomenclature_id, price_type)


@catalog_router.post(
    "/warehouse-price-history",
    status_code=status.HTTP_201_CREATED,
    summary="Создать запись истории цены",
)
def create_warehouse_price_history(
    payload: WarehousePriceHistoryCreate,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = CatalogService(CatalogRepository(db), RequestRepository(db))
    return service.create_price_history(payload)


@catalog_router.patch(
    "/warehouse-price-history/{row_id}",
    status_code=status.HTTP_200_OK,
    summary="Обновить запись истории цены",
)
def update_warehouse_price_history(
    row_id: str,
    payload: WarehousePriceHistoryUpdate,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = CatalogService(CatalogRepository(db), RequestRepository(db))
    return service.update_price_history(row_id, payload)


@catalog_router.delete(
    "/warehouse-price-history/{row_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить запись истории цены",
)
def delete_warehouse_price_history(
    row_id: str,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = CatalogService(CatalogRepository(db), RequestRepository(db))
    return service.delete_price_history(row_id)
