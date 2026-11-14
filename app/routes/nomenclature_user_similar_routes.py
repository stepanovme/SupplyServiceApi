from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.exceptions import HTTPException as StarletteHTTPException

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.session import SessionDB
from app.models.supply_request import NomenclatureUserSimilarCreate, NomenclatureUserSimilarUpdate
from app.repositories.catalog_repository import CatalogRepository
from app.repositories.nomenclature_user_similar_repository import NomenclatureUserSimilarRepository
from app.repositories.request_repository import RequestRepository
from app.services.catalog_service import CatalogService
from app.services.nomenclature_user_similar_service import NomenclatureUserSimilarService

nomenclature_user_similar_router = APIRouter(prefix="/nomenclature-user-similar", tags=["Nomenclature User Similar"])


def _build_nomenclature_fetcher(db):
    catalog_service = CatalogService(CatalogRepository(db), RequestRepository(db))
    def fetch(nid: str) -> dict | None:
        try:
            nomenclature = catalog_service.get_nomenclature_by_id(nid)
            stats = catalog_service.get_nomenclature_purchase_price_stats(nid)
            nomenclature["purchase_price_stats"] = stats
            return nomenclature
        except StarletteHTTPException:
            return None
    return fetch


def build_service(db: DbSupplySession, with_fetcher: bool = False) -> NomenclatureUserSimilarService:
    fetcher = _build_nomenclature_fetcher(db) if with_fetcher else None
    return NomenclatureUserSimilarService(NomenclatureUserSimilarRepository(db), nomenclature_fetcher=fetcher)


@nomenclature_user_similar_router.get("")
def get_my_similar(
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    return build_service(db, with_fetcher=True).get_by_user(str(_session.user_id))


@nomenclature_user_similar_router.get("/{similar_id}")
def get_similar(
    similar_id: int,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    result = build_service(db).get_by_id(similar_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return result


@nomenclature_user_similar_router.post("", status_code=status.HTTP_201_CREATED)
def create_similar(
    payload: NomenclatureUserSimilarCreate,
    db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    return build_service(db).create(payload, str(session.user_id))


@nomenclature_user_similar_router.patch("/{similar_id}")
def update_similar(
    similar_id: int,
    payload: NomenclatureUserSimilarUpdate,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    result = build_service(db).update(similar_id, payload)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return result


@nomenclature_user_similar_router.delete("/{similar_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_similar(
    similar_id: int,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    deleted = build_service(db).delete(similar_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return None
