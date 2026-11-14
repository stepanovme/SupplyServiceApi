from fastapi import APIRouter, Depends, Query, Response, status

from app.database import DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.estimate import ResourceType
from app.models.price_catalog import CatalogKind, FolderCreate, FolderUpdate, PriceItemCreate, PriceItemUpdate, TemplateResourceCreate, TemplateResourceUpdate
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.services.price_catalog_service import PriceCatalogService

price_catalog_router = APIRouter(prefix="/price-catalog", tags=["Price catalog"])


def build_service(kind: str, supply_db, reference_db) -> PriceCatalogService:
    return PriceCatalogService(supply_db, kind, ReferenceObjectRepository(reference_db))


# kind: works - справочник работ, resources - справочник ресурсов (материалы, механизмы, накладные, люди)
@price_catalog_router.get("/{kind}/tree", summary="Дерево папок справочника (без позиций)")
def get_tree(kind: CatalogKind, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(kind, supply_db, reference_db).get_tree()


@price_catalog_router.get("/{kind}/content", summary="Содержимое папки: подпапки и позиции (корень, если folder_id не задан)")
def get_content(kind: CatalogKind, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session), folder_id: int | None = Query(default=None)):
    return build_service(kind, supply_db, reference_db).get_content(folder_id)


@price_catalog_router.get("/{kind}/items", summary="Поиск позиций")
def search_items(
    kind: CatalogKind, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session),
    search: str | None = Query(default=None, description="По названию и шифру"), folder_id: int | None = Query(default=None),
    include_subfolders: bool = Query(default=True), type: ResourceType | None = Query(default=None, description="Только для resources"),
    limit: int = Query(default=50, ge=1, le=500), offset: int = Query(default=0, ge=0),
):
    return build_service(kind, supply_db, reference_db).search_items(search, folder_id, include_subfolders, type, limit, offset)


@price_catalog_router.post("/{kind}/folders", status_code=status.HTTP_201_CREATED, summary="Создать папку")
def create_folder(kind: CatalogKind, payload: FolderCreate, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(kind, supply_db, reference_db).create_folder(payload, str(_session.user_id))


@price_catalog_router.patch("/{kind}/folders/{folder_id}", summary="Переименовать / переместить папку")
def update_folder(kind: CatalogKind, folder_id: int, payload: FolderUpdate, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(kind, supply_db, reference_db).update_folder(folder_id, payload)


@price_catalog_router.delete("/{kind}/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить папку")
def delete_folder(kind: CatalogKind, folder_id: int, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session), recursive: bool = Query(default=False)):
    build_service(kind, supply_db, reference_db).delete_folder(folder_id, recursive)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@price_catalog_router.post("/{kind}/items", status_code=status.HTTP_201_CREATED, summary="Создать позицию")
def create_item(kind: CatalogKind, payload: PriceItemCreate, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(kind, supply_db, reference_db).create_item(payload, str(_session.user_id))


@price_catalog_router.get("/{kind}/items/{item_id}", summary="Позиция")
def get_item(kind: CatalogKind, item_id: int, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(kind, supply_db, reference_db).get_item(item_id)


@price_catalog_router.patch("/{kind}/items/{item_id}", summary="Изменить / переместить позицию")
def update_item(kind: CatalogKind, item_id: int, payload: PriceItemUpdate, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(kind, supply_db, reference_db).update_item(item_id, payload, str(_session.user_id))


@price_catalog_router.delete("/{kind}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить позицию")
def delete_item(kind: CatalogKind, item_id: int, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    build_service(kind, supply_db, reference_db).delete_item(item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# состав работы справочника (только kind=works)
@price_catalog_router.post("/{kind}/items/{item_id}/resources", status_code=status.HTTP_201_CREATED, summary="Добавить ресурс в состав работы справочника")
def add_template_resource(kind: CatalogKind, item_id: int, payload: TemplateResourceCreate, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(kind, supply_db, reference_db).add_template_resource(item_id, payload)


@price_catalog_router.patch("/{kind}/item-resources/{resource_id}", summary="Изменить ресурс в составе работы справочника")
def update_template_resource(kind: CatalogKind, resource_id: int, payload: TemplateResourceUpdate, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(kind, supply_db, reference_db).update_template_resource(resource_id, payload)


@price_catalog_router.delete("/{kind}/item-resources/{resource_id}", summary="Убрать ресурс из состава работы справочника")
def delete_template_resource(kind: CatalogKind, resource_id: int, supply_db: DbSupplySession, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(kind, supply_db, reference_db).delete_template_resource(resource_id)
