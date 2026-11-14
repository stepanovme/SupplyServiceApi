from fastapi import APIRouter, Depends, status

from app.database import DbAuthSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.object_expenditure import ObjectExpenditureCreate, ObjectExpenditureUpdate
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.object_expenditure_repository import ObjectExpenditureRepository
from app.services.object_expenditure_service import ObjectExpenditureService

object_expenditures_router = APIRouter(prefix="/object-expenditures", tags=["ObjectExpenditures"])


def build_service(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession | None = None,
) -> ObjectExpenditureService:
    return ObjectExpenditureService(
        ObjectExpenditureRepository(supply_db),
        AuthUserRepository(auth_db) if auth_db else None,
    )


@object_expenditures_router.get(
    "/by-object/{object_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить список расходов по объекту",
)
def get_expenditures_by_object(
    object_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).get_by_object(object_id)


@object_expenditures_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать расход по объекту",
)
def create_expenditure(
    payload: ObjectExpenditureCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).create(payload, _session.user_id)


@object_expenditures_router.patch(
    "/{expenditure_id}",
    status_code=status.HTTP_200_OK,
    summary="Изменить расход по объекту",
)
def update_expenditure(
    expenditure_id: int,
    payload: ObjectExpenditureUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).update(expenditure_id, payload)


@object_expenditures_router.delete(
    "/{expenditure_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить расход по объекту",
)
def delete_expenditure(
    expenditure_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete(expenditure_id)
    return None
