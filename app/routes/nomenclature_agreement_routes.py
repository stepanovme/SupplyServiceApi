from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.session import SessionDB
from app.models.supply_request import NomenclatureAgreementCreate, NomenclatureAgreementUpdate
from app.repositories.nomenclature_agreement_repository import NomenclatureAgreementRepository
from app.services.nomenclature_agreement_service import NomenclatureAgreementService

nomenclature_agreement_router = APIRouter(prefix="/nomenclature-agreements", tags=["Nomenclature Agreements"])


def build_service(db: DbSupplySession) -> NomenclatureAgreementService:
    return NomenclatureAgreementService(NomenclatureAgreementRepository(db))


@nomenclature_agreement_router.get("")
def get_agreements_by_nomenclature(
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
    nomenclature_id: str = Query(...),
):
    return build_service(db).get_by_nomenclature(nomenclature_id)


@nomenclature_agreement_router.get("/{agreement_id}")
def get_agreement(
    agreement_id: str,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    result = build_service(db).get_by_id(agreement_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agreement not found")
    return result


@nomenclature_agreement_router.post("", status_code=status.HTTP_201_CREATED)
def create_agreement(
    payload: NomenclatureAgreementCreate,
    db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    return build_service(db).create(payload, str(session.user_id))


@nomenclature_agreement_router.patch("/{agreement_id}")
def update_agreement(
    agreement_id: str,
    payload: NomenclatureAgreementUpdate,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    result = build_service(db).update(agreement_id, payload)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agreement not found")
    return result


@nomenclature_agreement_router.delete("/{agreement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agreement(
    agreement_id: str,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    deleted = build_service(db).delete(agreement_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agreement not found")
    return None
