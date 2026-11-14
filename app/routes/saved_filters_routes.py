from fastapi import APIRouter, Depends, status

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.saved_filter import SavedFilterCreate, SavedFilterUpdate
from app.models.session import SessionDB
from app.repositories.saved_filter_repository import SavedFilterRepository
from app.services.saved_filter_service import SavedFilterService

saved_filters_router = APIRouter(prefix="/saved-filters", tags=["SavedFilters"])


@saved_filters_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Получить список сохранённых фильтров текущего пользователя",
)
def get_saved_filters(
    db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    service = SavedFilterService(SavedFilterRepository(db))
    return service.get_by_user(str(session.user_id))


@saved_filters_router.get(
    "/{item_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить сохранённый фильтр по ID",
)
def get_saved_filter(
    item_id: str,
    db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    service = SavedFilterService(SavedFilterRepository(db))
    return service.get_by_id(item_id, str(session.user_id))


@saved_filters_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать сохранённый фильтр",
)
def create_saved_filter(
    data: SavedFilterCreate,
    db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    service = SavedFilterService(SavedFilterRepository(db))
    return service.create(data, str(session.user_id))


@saved_filters_router.patch(
    "/{item_id}",
    status_code=status.HTTP_200_OK,
    summary="Обновить сохранённый фильтр",
)
def update_saved_filter(
    item_id: str,
    data: SavedFilterUpdate,
    db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    service = SavedFilterService(SavedFilterRepository(db))
    return service.update(item_id, data, str(session.user_id))


@saved_filters_router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить сохранённый фильтр",
)
def delete_saved_filter(
    item_id: str,
    db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    service = SavedFilterService(SavedFilterRepository(db))
    service.delete(item_id, str(session.user_id))
