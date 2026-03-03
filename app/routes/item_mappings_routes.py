from fastapi import APIRouter, Depends, status

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.item_mapping import ItemMappingAutoMatchRequest, ItemMappingCreate, ItemMappingUpdate
from app.repositories.item_mapping_repository import ItemMappingRepository
from app.services.item_mapping_service import ItemMappingService

item_mappings_router = APIRouter(prefix="/item-mappings", tags=["ItemMappings"])


def build_service(db: DbSupplySession) -> ItemMappingService:
    return ItemMappingService(ItemMappingRepository(db))


@item_mappings_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Получить связки позиции заявки и позиции счета",
)
def get_item_mappings(
    db: DbSupplySession,
    request_id: int | None = None,
    invoice_id: int | None = None,
    request_item_id: str | None = None,
    invoice_item_id: str | None = None,
    _session=Depends(get_session),
):
    service = build_service(db)
    return service.list(
        request_id=request_id,
        invoice_id=invoice_id,
        request_item_id=request_item_id,
        invoice_item_id=invoice_item_id,
    )


@item_mappings_router.get(
    "/{mapping_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить связку по id",
)
def get_item_mapping_by_id(
    mapping_id: str,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_service(db)
    return service.get_by_id(mapping_id)


@item_mappings_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать связку позиции заявки и счета",
)
def create_item_mapping(
    payload: ItemMappingCreate,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_service(db)
    return service.create(payload)


@item_mappings_router.patch(
    "/{mapping_id}",
    status_code=status.HTTP_200_OK,
    summary="Редактировать связку позиции заявки и счета",
)
def update_item_mapping(
    mapping_id: str,
    payload: ItemMappingUpdate,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_service(db)
    return service.update(mapping_id, payload)


@item_mappings_router.delete(
    "/{mapping_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить связку позиции заявки и счета",
)
def delete_item_mapping(
    mapping_id: str,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_service(db)
    service.delete(mapping_id)
    return None


@item_mappings_router.post(
    "/auto-match",
    status_code=status.HTTP_200_OK,
    summary="Автоматическое сопоставление позиций request и invoice через Mistral",
)
def auto_match_item_mappings(
    payload: ItemMappingAutoMatchRequest,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_service(db)
    return service.auto_match(request_id=payload.request_id, invoice_id=payload.invoice_id)
