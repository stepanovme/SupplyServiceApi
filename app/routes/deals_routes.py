from fastapi import APIRouter, Depends, status

from app.database import DbAuthSession, DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.session import SessionDB
from app.models.deal import (
    DealCreate,
    DealDeliveryCreate,
    DealDeliveryUpdate,
    DealProductCreate,
    DealProductUpdate,
    DealServiceCreate,
    DealServiceUpdate,
    DealUpdate,
)
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.counterparty_repository import CounterpartyRepository
from app.repositories.deal_repository import DealRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.services.deal_service import DealServiceManager

deals_router = APIRouter(prefix="/deals", tags=["Deals"])


def _service(
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    auth_db: DbAuthSession,
) -> DealServiceManager:
    return DealServiceManager(
        DealRepository(db),
        CounterpartyRepository(reference_db),
        ReferenceObjectRepository(reference_db),
        AuthUserRepository(auth_db),
    )


@deals_router.get("", status_code=status.HTTP_200_OK, summary="Получить список сделок")
def get_deals(
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return _service(db, reference_db, auth_db).get_deals()


@deals_router.get("/{deal_id}", status_code=status.HTTP_200_OK, summary="Получить сделку по id")
def get_deal(
    deal_id: str,
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return _service(db, reference_db, auth_db).get_deal(deal_id)


@deals_router.post("", status_code=status.HTTP_201_CREATED, summary="Создать сделку")
def create_deal(
    payload: DealCreate,
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    auth_db: DbAuthSession,
    session: SessionDB = Depends(get_session),
):
    return _service(db, reference_db, auth_db).create_deal(payload, str(session.user_id))


@deals_router.patch("/{deal_id}", status_code=status.HTTP_200_OK, summary="Обновить сделку")
def update_deal(
    deal_id: str,
    payload: DealUpdate,
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return _service(db, reference_db, auth_db).update_deal(deal_id, payload)


@deals_router.delete("/{deal_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить сделку")
def delete_deal(
    deal_id: str,
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return _service(db, reference_db, auth_db).delete_deal(deal_id)


@deals_router.get("/{deal_id}/deliveries", status_code=status.HTTP_200_OK, summary="Получить доставки сделки")
def get_deal_deliveries(
    deal_id: str,
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return _service(db, reference_db, auth_db).get_deal_deliveries(deal_id)


@deals_router.post("/{deal_id}/deliveries", status_code=status.HTTP_201_CREATED, summary="Создать доставку сделки")
def create_deal_delivery(
    deal_id: str,
    payload: DealDeliveryCreate,
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return _service(db, reference_db, auth_db).create_deal_delivery(deal_id, payload)


@deals_router.patch("/{deal_id}/deliveries/{delivery_id}", status_code=status.HTTP_200_OK, summary="Обновить доставку сделки")
def update_deal_delivery(
    deal_id: str,
    delivery_id: str,
    payload: DealDeliveryUpdate,
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return _service(db, reference_db, auth_db).update_deal_delivery(deal_id, delivery_id, payload)


@deals_router.delete("/{deal_id}/deliveries/{delivery_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить доставку сделки")
def delete_deal_delivery(
    deal_id: str,
    delivery_id: str,
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return _service(db, reference_db, auth_db).delete_deal_delivery(deal_id, delivery_id)


@deals_router.get("/{deal_id}/products", status_code=status.HTTP_200_OK, summary="Получить товары сделки")
def get_deal_products(
    deal_id: str,
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return _service(db, reference_db, auth_db).get_deal_products(deal_id)


@deals_router.post("/{deal_id}/products", status_code=status.HTTP_201_CREATED, summary="Создать товар сделки")
def create_deal_product(
    deal_id: str,
    payload: DealProductCreate,
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return _service(db, reference_db, auth_db).create_deal_product(deal_id, payload)


@deals_router.patch("/{deal_id}/products/{product_id}", status_code=status.HTTP_200_OK, summary="Обновить товар сделки")
def update_deal_product(
    deal_id: str,
    product_id: str,
    payload: DealProductUpdate,
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return _service(db, reference_db, auth_db).update_deal_product(deal_id, product_id, payload)


@deals_router.delete("/{deal_id}/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить товар сделки")
def delete_deal_product(
    deal_id: str,
    product_id: str,
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return _service(db, reference_db, auth_db).delete_deal_product(deal_id, product_id)


@deals_router.get("/{deal_id}/services", status_code=status.HTTP_200_OK, summary="Получить услуги сделки")
def get_deal_services(
    deal_id: str,
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return _service(db, reference_db, auth_db).get_deal_services(deal_id)


@deals_router.post("/{deal_id}/services", status_code=status.HTTP_201_CREATED, summary="Создать услугу сделки")
def create_deal_service(
    deal_id: str,
    payload: DealServiceCreate,
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return _service(db, reference_db, auth_db).create_deal_service(deal_id, payload)


@deals_router.patch("/{deal_id}/services/{service_id}", status_code=status.HTTP_200_OK, summary="Обновить услугу сделки")
def update_deal_service(
    deal_id: str,
    service_id: str,
    payload: DealServiceUpdate,
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return _service(db, reference_db, auth_db).update_deal_service(deal_id, service_id, payload)


@deals_router.delete("/{deal_id}/services/{service_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить услугу сделки")
def delete_deal_service(
    deal_id: str,
    service_id: str,
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return _service(db, reference_db, auth_db).delete_deal_service(deal_id, service_id)
