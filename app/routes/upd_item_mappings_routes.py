from fastapi import APIRouter, Depends, status

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.upd_item_mapping import (
    UpdItemMappingAutoMatchRequest,
    UpdItemMappingCreate,
    UpdItemMappingUpdate,
)
from app.repositories.upd_item_mapping_repository import UpdItemMappingRepository
from app.services.upd_item_mapping_service import UpdItemMappingService

upd_item_mappings_router = APIRouter(prefix="/upd-item-mappings", tags=["UpdItemMappings"])


def build_service(db: DbSupplySession) -> UpdItemMappingService:
    return UpdItemMappingService(UpdItemMappingRepository(db))


@upd_item_mappings_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Получить связки позиции УПД и номенклатуры",
)
def get_upd_item_mappings(
    db: DbSupplySession,
    upd_documents_id: str | None = None,
    upd_documents_item_id: str | None = None,
    nomenclature_id: str | None = None,
    _session=Depends(get_session),
):
    service = build_service(db)
    return service.list(
        upd_documents_id=upd_documents_id,
        upd_documents_item_id=upd_documents_item_id,
        nomenclature_id=nomenclature_id,
    )


@upd_item_mappings_router.get(
    "/{mapping_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить связку УПД позиции и номенклатуры по id",
)
def get_upd_item_mapping_by_id(
    mapping_id: str,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_service(db)
    return service.get_by_id(mapping_id)


@upd_item_mappings_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать связку позиции УПД и номенклатуры",
)
def create_upd_item_mapping(
    payload: UpdItemMappingCreate,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_service(db)
    return service.create(payload)


@upd_item_mappings_router.patch(
    "/{mapping_id}",
    status_code=status.HTTP_200_OK,
    summary="Редактировать связку позиции УПД и номенклатуры",
)
def update_upd_item_mapping(
    mapping_id: str,
    payload: UpdItemMappingUpdate,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_service(db)
    return service.update(mapping_id, payload)


@upd_item_mappings_router.delete(
    "/{mapping_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить связку позиции УПД и номенклатуры",
)
def delete_upd_item_mapping(
    mapping_id: str,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_service(db)
    service.delete(mapping_id)
    return None


@upd_item_mappings_router.post(
    "/auto-match",
    status_code=status.HTTP_200_OK,
    summary="Автоматическое сопоставление позиций УПД и номенклатуры по названию",
)
def auto_match_upd_item_mappings(
    payload: UpdItemMappingAutoMatchRequest,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_service(db)
    return service.auto_match(payload)
