from fastapi import APIRouter, Depends, Query, status

from app.database import DbAuthSession, DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.delivery import (
    DeliveryCreate,
    DeliveryItemCreate,
    DeliveryItemUpdate,
    DeliveryUpdate,
)
from app.models.session import SessionDB
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.counterparty_repository import CounterpartyRepository
from app.repositories.delivery_repository import DeliveryRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.services.delivery_service import DeliveryService

deliveries_router = APIRouter(prefix="/deliveries", tags=["Deliveries"])


def _service(
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    auth_db: DbAuthSession,
) -> DeliveryService:
    return DeliveryService(
        DeliveryRepository(db),
        CounterpartyRepository(reference_db),
        AuthUserRepository(auth_db),
        ReferenceObjectRepository(reference_db),
    )


@deliveries_router.get("", status_code=status.HTTP_200_OK, summary="Получить список доставок")
def get_deliveries(
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    auth_db: DbAuthSession,
    delivery_from: str | None = Query(default=None, description="Фильтр по откуда"),
    delivery_to: str | None = Query(default=None, description="Фильтр по куда"),
    _session=Depends(get_session),
):
    return _service(db, reference_db, auth_db).get_deliveries(
        delivery_from=delivery_from,
        delivery_to=delivery_to,
    )


@deliveries_router.get("/{delivery_id}", status_code=status.HTTP_200_OK, summary="Получить доставку по id")
def get_delivery(
    delivery_id: str,
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return _service(db, reference_db, auth_db).get_delivery(delivery_id)


@deliveries_router.post("", status_code=status.HTTP_201_CREATED, summary="Создать доставку")
def create_delivery(
    payload: DeliveryCreate,
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    auth_db: DbAuthSession,
    session: SessionDB = Depends(get_session),
):
    return _service(db, reference_db, auth_db).create_delivery(payload, str(session.user_id))


@deliveries_router.patch("/{delivery_id}", status_code=status.HTTP_200_OK, summary="Обновить доставку")
def update_delivery(
    delivery_id: str,
    payload: DeliveryUpdate,
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return _service(db, reference_db, auth_db).update_delivery(delivery_id, payload)


@deliveries_router.delete("/{delivery_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить доставку")
def delete_delivery(
    delivery_id: str,
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return _service(db, reference_db, auth_db).delete_delivery(delivery_id)


@deliveries_router.get("/{delivery_id}/items", status_code=status.HTTP_200_OK, summary="Получить позиции доставки")
def get_delivery_items(
    delivery_id: str,
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return _service(db, reference_db, auth_db).get_delivery_items(delivery_id)


@deliveries_router.post("/{delivery_id}/items", status_code=status.HTTP_201_CREATED, summary="Создать позицию доставки")
def create_delivery_item(
    delivery_id: str,
    payload: DeliveryItemCreate,
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    auth_db: DbAuthSession,
    session: SessionDB = Depends(get_session),
):
    return _service(db, reference_db, auth_db).create_delivery_item(delivery_id, payload, str(session.user_id))


@deliveries_router.patch("/{delivery_id}/items/{item_id}", status_code=status.HTTP_200_OK, summary="Обновить позицию доставки")
def update_delivery_item(
    delivery_id: str,
    item_id: str,
    payload: DeliveryItemUpdate,
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return _service(db, reference_db, auth_db).update_delivery_item(delivery_id, item_id, payload)


@deliveries_router.delete("/{delivery_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить позицию доставки")
def delete_delivery_item(
    delivery_id: str,
    item_id: str,
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return _service(db, reference_db, auth_db).delete_delivery_item(delivery_id, item_id)
