from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.session import SessionDB
from app.models.supply_request import NomenclatureGroupCreate, NomenclatureGroupUpdate
from app.repositories.nomenclature_group_repository import NomenclatureGroupRepository
from app.services.nomenclature_group_service import NomenclatureGroupService

nomenclature_group_router = APIRouter(prefix="/nomenclature-groups", tags=["Nomenclature Groups"])


class NomenclatureGroupItemCreate(BaseModel):
    nomenclature_group_id: int
    nomenclature_id: str


def build_service(supply_db: DbSupplySession) -> NomenclatureGroupService:
    return NomenclatureGroupService(NomenclatureGroupRepository(supply_db), supply_db=supply_db)


# --- Groups CRUD ---

@nomenclature_group_router.get("")
def get_all_groups(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).get_all()


@nomenclature_group_router.get("/{group_id}")
def get_group(
    group_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    result = build_service(supply_db).get_by_id(group_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return result


@nomenclature_group_router.post("", status_code=status.HTTP_201_CREATED)
def create_group(
    payload: NomenclatureGroupCreate,
    supply_db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    return build_service(supply_db).create(payload, str(session.user_id))


@nomenclature_group_router.patch("/{group_id}")
def update_group(
    group_id: int,
    payload: NomenclatureGroupUpdate,
    supply_db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    result = build_service(supply_db).update(group_id, payload, str(session.user_id))
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return result


@nomenclature_group_router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    deleted = build_service(supply_db).delete(group_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return None


# --- Group Items CRUD ---

@nomenclature_group_router.get("/{group_id}/items")
def get_group_items(
    group_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).get_items_by_group(group_id)


@nomenclature_group_router.get("/items/{item_id}")
def get_group_item(
    item_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    result = build_service(supply_db).get_item(item_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return result


@nomenclature_group_router.post("/items", status_code=status.HTTP_201_CREATED)
def create_group_item(
    payload: NomenclatureGroupItemCreate,
    supply_db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    return build_service(supply_db).create_item(
        payload.nomenclature_group_id,
        payload.nomenclature_id,
        str(session.user_id),
    )


@nomenclature_group_router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group_item(
    item_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    deleted = build_service(supply_db).delete_item(item_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return None


# --- Special endpoints ---

@nomenclature_group_router.get("/{group_id}/nomenclatures")
def get_group_nomenclatures(
    group_id: int,
    supply_db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    result = build_service(supply_db).get_group_nomenclature(group_id, user_id=str(session.user_id))
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return result


@nomenclature_group_router.get("/{group_id}/warehouse-list")
def get_group_warehouse_list(
    group_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    result = build_service(supply_db).get_group_warehouse_list(group_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return result
