from fastapi import APIRouter, Depends, status

from app.database import DbReferenceSession, DbSupplySession
from app.repositories.counterparty_repository import CounterpartyRepository
from app.middleware.auth_middleware import get_session
from app.models.session import SessionDB
from app.models.invoice_outgoing import (
    InvoiceOutgoingCreate,
    InvoiceOutgoingItemCreate,
    InvoiceOutgoingItemUpdate,
    InvoiceOutgoingNomenclatureCreate,
    InvoiceOutgoingNomenclatureUpdate,
    InvoiceOutgoingUnitCreate,
    InvoiceOutgoingUnitUpdate,
    InvoiceOutgoingUpdate,
)
from app.repositories.invoice_outgoing_repository import InvoiceOutgoingRepository
from app.services.invoice_outgoing_service import InvoiceOutgoingService

invoice_outgoing_router = APIRouter(prefix="/invoice-outgoing", tags=["InvoiceOutgoing"])


def build_invoice_outgoing_service(
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession | None = None,
) -> InvoiceOutgoingService:
    counterparty_repo = CounterpartyRepository(reference_db) if reference_db else None
    return InvoiceOutgoingService(
        InvoiceOutgoingRepository(supply_db),
        counterparty_repo=counterparty_repo,
    )


@invoice_outgoing_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Получить список исходящих счетов",
)
def get_invoice_outgoings(
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_invoice_outgoing_service(supply_db, reference_db)
    return service.get_outgoings()


@invoice_outgoing_router.get(
    "/{outgoing_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить исходящий счет",
)
def get_invoice_outgoing(
    outgoing_id: int,
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = build_invoice_outgoing_service(supply_db, reference_db)
    return service.get_outgoing(outgoing_id)


@invoice_outgoing_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать исходящий счет",
)
def create_invoice_outgoing(
    payload: InvoiceOutgoingCreate,
    supply_db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    service = build_invoice_outgoing_service(supply_db)
    return service.create_outgoing(payload, str(session.user_id))


@invoice_outgoing_router.patch(
    "/{outgoing_id}",
    status_code=status.HTTP_200_OK,
    summary="Изменить исходящий счет",
)
def update_invoice_outgoing(
    outgoing_id: int,
    payload: InvoiceOutgoingUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_invoice_outgoing_service(supply_db)
    return service.update_outgoing(outgoing_id, payload)


@invoice_outgoing_router.delete(
    "/{outgoing_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить исходящий счет",
)
def delete_invoice_outgoing(
    outgoing_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_invoice_outgoing_service(supply_db)
    service.delete_outgoing(outgoing_id)
    return None


@invoice_outgoing_router.get(
    "/{outgoing_id}/items",
    status_code=status.HTTP_200_OK,
    summary="Получить позиции исходящего счета",
)
def get_invoice_outgoing_items(
    outgoing_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_invoice_outgoing_service(supply_db)
    return service.get_outgoing_items(outgoing_id)


@invoice_outgoing_router.post(
    "/{outgoing_id}/items",
    status_code=status.HTTP_201_CREATED,
    summary="Создать позицию исходящего счета",
)
def create_invoice_outgoing_item(
    outgoing_id: int,
    payload: InvoiceOutgoingItemCreate,
    supply_db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    service = build_invoice_outgoing_service(supply_db)
    return service.create_outgoing_item(outgoing_id, payload, str(session.user_id))


@invoice_outgoing_router.patch(
    "/{outgoing_id}/items/{item_id}",
    status_code=status.HTTP_200_OK,
    summary="Изменить позицию исходящего счета",
)
def update_invoice_outgoing_item(
    outgoing_id: int,
    item_id: int,
    payload: InvoiceOutgoingItemUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_invoice_outgoing_service(supply_db)
    return service.update_outgoing_item(outgoing_id, item_id, payload)


@invoice_outgoing_router.delete(
    "/{outgoing_id}/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить позицию исходящего счета",
)
def delete_invoice_outgoing_item(
    outgoing_id: int,
    item_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_invoice_outgoing_service(supply_db)
    service.delete_outgoing_item(outgoing_id, item_id)
    return None


@invoice_outgoing_router.get(
    "/nomenclatures",
    status_code=status.HTTP_200_OK,
    summary="Получить список номенклатур",
)
def get_invoice_outgoing_nomenclatures(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_invoice_outgoing_service(supply_db)
    return service.get_nomenclatures()


@invoice_outgoing_router.get(
    "/nomenclatures/{nomen_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить номенклатуру",
)
def get_invoice_outgoing_nomenclature(
    nomen_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_invoice_outgoing_service(supply_db)
    return service.get_nomenclature(nomen_id)


@invoice_outgoing_router.post(
    "/nomenclatures",
    status_code=status.HTTP_201_CREATED,
    summary="Создать номенклатуру",
)
def create_invoice_outgoing_nomenclature(
    payload: InvoiceOutgoingNomenclatureCreate,
    supply_db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    service = build_invoice_outgoing_service(supply_db)
    return service.create_nomenclature(payload, str(session.user_id))


@invoice_outgoing_router.patch(
    "/nomenclatures/{nomen_id}",
    status_code=status.HTTP_200_OK,
    summary="Изменить номенклатуру",
)
def update_invoice_outgoing_nomenclature(
    nomen_id: str,
    payload: InvoiceOutgoingNomenclatureUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_invoice_outgoing_service(supply_db)
    return service.update_nomenclature(nomen_id, payload)


@invoice_outgoing_router.delete(
    "/nomenclatures/{nomen_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить номенклатуру",
)
def delete_invoice_outgoing_nomenclature(
    nomen_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_invoice_outgoing_service(supply_db)
    service.delete_nomenclature(nomen_id)
    return None


@invoice_outgoing_router.get(
    "/units",
    status_code=status.HTTP_200_OK,
    summary="Получить список единиц измерения",
)
def get_invoice_outgoing_units(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_invoice_outgoing_service(supply_db)
    return service.get_units()


@invoice_outgoing_router.get(
    "/units/{unit_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить единицу измерения",
)
def get_invoice_outgoing_unit(
    unit_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_invoice_outgoing_service(supply_db)
    return service.get_unit(unit_id)


@invoice_outgoing_router.post(
    "/units",
    status_code=status.HTTP_201_CREATED,
    summary="Создать единицу измерения",
)
def create_invoice_outgoing_unit(
    payload: InvoiceOutgoingUnitCreate,
    supply_db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    service = build_invoice_outgoing_service(supply_db)
    return service.create_unit(payload, str(session.user_id))


@invoice_outgoing_router.patch(
    "/units/{unit_id}",
    status_code=status.HTTP_200_OK,
    summary="Изменить единицу измерения",
)
def update_invoice_outgoing_unit(
    unit_id: str,
    payload: InvoiceOutgoingUnitUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_invoice_outgoing_service(supply_db)
    return service.update_unit(unit_id, payload)


@invoice_outgoing_router.delete(
    "/units/{unit_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить единицу измерения",
)
def delete_invoice_outgoing_unit(
    unit_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_invoice_outgoing_service(supply_db)
    service.delete_unit(unit_id)
    return None
