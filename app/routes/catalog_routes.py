from fastapi import APIRouter, Depends, Query, status

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
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
