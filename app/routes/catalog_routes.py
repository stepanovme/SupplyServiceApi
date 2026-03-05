from fastapi import APIRouter, Depends, Query, status

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.session import SessionDB
from app.models.supply_request import (
    NomenclatureCreate,
    NomenclatureUpdate,
    WarehouseCategoryCreate,
    WarehouseCategoryUpdate,
)
from app.repositories.catalog_repository import CatalogRepository
from app.repositories.request_repository import RequestRepository
from app.services.catalog_service import CatalogService

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
