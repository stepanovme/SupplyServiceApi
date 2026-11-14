from fastapi import APIRouter, Depends, Query, status

from app.database import DbAuthSession, DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.receipt_contract import ReceiptContractCreate, ReceiptContractUpdate
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.contract_repository import ContractRepository
from app.repositories.receipt_contract_repository import ReceiptContractRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.services.receipt_contract_service import ReceiptContractService

receipt_contracts_router = APIRouter(prefix="/receipt-contracts", tags=["ReceiptContracts"])


def build_service(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession | None = None,
    reference_db: DbReferenceSession | None = None,
) -> ReceiptContractService:
    return ReceiptContractService(
        ReceiptContractRepository(supply_db),
        AuthUserRepository(auth_db) if auth_db else None,
        ContractRepository(supply_db),
        ReferenceObjectRepository(reference_db) if reference_db else None,
    )


@receipt_contracts_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Получить список поступлений по договору",
)
def get_receipts_by_contract(
    contract_id: int = Query(...),
    supply_db: DbSupplySession = None,
    auth_db: DbAuthSession = None,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).get_by_contract(contract_id)


@receipt_contracts_router.get(
    "/by-object/{object_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить список поступлений по объекту",
)
def get_receipts_by_object(
    object_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_by_object(object_id)


@receipt_contracts_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать поступление по договору",
)
def create_receipt(
    payload: ReceiptContractCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).create(payload, _session.user_id)


@receipt_contracts_router.patch(
    "/{receipt_id}",
    status_code=status.HTTP_200_OK,
    summary="Изменить поступление по договору",
)
def update_receipt(
    receipt_id: int,
    payload: ReceiptContractUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).update(receipt_id, payload)


@receipt_contracts_router.delete(
    "/{receipt_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить поступление по договору",
)
def delete_receipt(
    receipt_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete(receipt_id)
    return None
