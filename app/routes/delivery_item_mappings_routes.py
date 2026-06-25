from fastapi import APIRouter, Depends, status

from app.database import DbAuthSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.delivery_item_mapping import (
    DeliveryItemMappingAutoMatchRequest,
    DeliveryItemMappingCreate,
    DeliveryItemMappingUpdate,
)
from app.models.session import SessionDB
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.delivery_item_mapping_repository import DeliveryItemMappingRepository
from app.services.delivery_item_mapping_service import DeliveryItemMappingService

delivery_item_mappings_router = APIRouter(prefix="/delivery-item-mappings", tags=["DeliveryItemMappings"])


def build_service(db: DbSupplySession, auth_db: DbAuthSession) -> DeliveryItemMappingService:
    return DeliveryItemMappingService(
        DeliveryItemMappingRepository(db),
        AuthUserRepository(auth_db),
    )


@delivery_item_mappings_router.get("", status_code=status.HTTP_200_OK, summary="Получить связки delivery и nomenclature")
def get_delivery_item_mappings(
    db: DbSupplySession,
    auth_db: DbAuthSession,
    delivery_id: str | None = None,
    delivery_item_id: str | None = None,
    nomenclature_id: str | None = None,
    _session=Depends(get_session),
):
    return build_service(db, auth_db).list(
        delivery_id=delivery_id,
        delivery_item_id=delivery_item_id,
        nomenclature_id=nomenclature_id,
    )


@delivery_item_mappings_router.get("/{mapping_id}", status_code=status.HTTP_200_OK, summary="Получить связку по id")
def get_delivery_item_mapping_by_id(
    mapping_id: str,
    db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(db, auth_db).get_by_id(mapping_id)


@delivery_item_mappings_router.post("", status_code=status.HTTP_201_CREATED, summary="Создать связку delivery и nomenclature")
def create_delivery_item_mapping(
    payload: DeliveryItemMappingCreate,
    db: DbSupplySession,
    auth_db: DbAuthSession,
    session: SessionDB = Depends(get_session),
):
    return build_service(db, auth_db).create(payload, str(session.user_id))


@delivery_item_mappings_router.post(
    "/auto-match",
    status_code=status.HTTP_200_OK,
    summary="Автоматически сопоставить delivery items с nomenclature через Mistral",
)
def auto_match_delivery_item_mappings(
    payload: DeliveryItemMappingAutoMatchRequest,
    db: DbSupplySession,
    auth_db: DbAuthSession,
    session: SessionDB = Depends(get_session),
):
    return build_service(db, auth_db).auto_match(payload, str(session.user_id))


@delivery_item_mappings_router.patch("/{mapping_id}", status_code=status.HTTP_200_OK, summary="Обновить связку delivery и nomenclature")
def update_delivery_item_mapping(
    mapping_id: str,
    payload: DeliveryItemMappingUpdate,
    db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(db, auth_db).update(mapping_id, payload)


@delivery_item_mappings_router.delete("/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить связку delivery и nomenclature")
def delete_delivery_item_mapping(
    mapping_id: str,
    db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    build_service(db, auth_db).delete(mapping_id)
    return None
