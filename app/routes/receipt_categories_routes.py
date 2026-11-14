from typing import Literal

from fastapi import APIRouter, Depends, Query, status

from app.database import DbAuthSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.receipt_category import ReceiptCategoryCreate, ReceiptCategoryUpdate
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.receipt_category_repository import ReceiptCategoryRepository
from app.services.receipt_category_service import ReceiptCategoryService

receipt_categories_router = APIRouter(prefix="/receipt-categories", tags=["ReceiptCategories"])


def build_service(supply_db: DbSupplySession, auth_db: DbAuthSession) -> ReceiptCategoryService:
    return ReceiptCategoryService(ReceiptCategoryRepository(supply_db), AuthUserRepository(auth_db))


@receipt_categories_router.get(
    "",
    summary="Категории чеков, доступные мне: стандартные и мои личные",
    description="scope: all (по умолчанию) | system (только стандартные) | mine (только мои). `can_edit` — могу ли я менять категорию.",
)
def get_receipt_categories(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    scope: Literal["all", "system", "mine"] = Query(default="all"),
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).get_list(_session.user_id, scope)


@receipt_categories_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать категорию чеков (личную или, для администратора, стандартную)",
)
def create_receipt_category(
    payload: ReceiptCategoryCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).create(payload, _session.user_id)


@receipt_categories_router.get("/{category_id}", summary="Получить категорию чеков")
def get_receipt_category(
    category_id: str, supply_db: DbSupplySession, auth_db: DbAuthSession, _session=Depends(get_session)
):
    return build_service(supply_db, auth_db).get_by_id(category_id, _session.user_id)


@receipt_categories_router.patch(
    "/{category_id}",
    summary="Изменить название/цвет категории",
    description="Личную меняет её владелец, стандартную — администратор. color = null убирает цвет.",
)
def update_receipt_category(
    category_id: str,
    payload: ReceiptCategoryUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).update(category_id, payload, _session.user_id)


@receipt_categories_router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить категорию",
    description="Если категория привязана к чекам — 409 с числом чеков; с force=true она удаляется и снимается со всех чеков.",
)
def delete_receipt_category(
    category_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    force: bool = Query(default=False),
    _session=Depends(get_session),
):
    build_service(supply_db, auth_db).delete(category_id, _session.user_id, force)
    return None
