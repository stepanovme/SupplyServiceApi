from fastapi import APIRouter, Depends, Query, status

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.document_access_setting import (
    DocumentAccessSettingCreate,
    DocumentAccessSettingUpdate,
)
from app.repositories.department_repository import DepartmentRepository
from app.repositories.document_access_setting_repository import DocumentAccessSettingRepository
from app.services.document_access_setting_service import DocumentAccessSettingService

document_access_settings_router = APIRouter(prefix="/document-access-settings", tags=["DocumentAccessSettings"])


def build_service(db: DbSupplySession) -> DocumentAccessSettingService:
    return DocumentAccessSettingService(
        DocumentAccessSettingRepository(db),
        DepartmentRepository(db),
    )


# ── List / Get ───────────────────────────────────────────────────────────────

@document_access_settings_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Список всех настроек видимости",
)
def get_all_settings(
    db: DbSupplySession,
    _session=Depends(get_session),
    document_type: str | None = Query(default=None),
):
    return build_service(db).get_all(document_type)


@document_access_settings_router.get(
    "/{setting_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить настройку видимости",
)
def get_setting(
    setting_id: str,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(db).get_by_id(setting_id)


@document_access_settings_router.get(
    "/by-target/user/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Все настройки конкретного пользователя",
)
def get_settings_by_user(
    user_id: str,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(db).get_settings_by_target(user_id=user_id)


@document_access_settings_router.get(
    "/by-target/department/{department_id}",
    status_code=status.HTTP_200_OK,
    summary="Все настройки конкретного отдела",
)
def get_settings_by_department(
    department_id: int,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(db).get_settings_by_target(department_id=department_id)


# ── CRUD ─────────────────────────────────────────────────────────────────────

@document_access_settings_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать настройку видимости",
)
def create_setting(
    payload: DocumentAccessSettingCreate,
    db: DbSupplySession,
    session=Depends(get_session),
):
    return build_service(db).create(payload, str(session.user_id))


@document_access_settings_router.patch(
    "/{setting_id}",
    status_code=status.HTTP_200_OK,
    summary="Обновить настройку видимости",
)
def update_setting(
    setting_id: str,
    payload: DocumentAccessSettingUpdate,
    db: DbSupplySession,
    session=Depends(get_session),
):
    return build_service(db).update(setting_id, payload, str(session.user_id))


@document_access_settings_router.delete(
    "/{setting_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить настройку видимости",
)
def delete_setting(
    setting_id: str,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(db).delete(setting_id)
    return None


# ── Bulk: сохранить все настройки для пользователя/отдела за раз ─────────────

@document_access_settings_router.post(
    "/bulk",
    status_code=status.HTTP_200_OK,
    summary="Массовое сохранение настроек для пользователя/отдела",
)
def bulk_save_settings(
    payload: dict,
    db: DbSupplySession,
    session=Depends(get_session),
):
    service = build_service(db)
    target_user_id = payload.get("user_id")
    target_department_id = payload.get("department_id")
    raw_settings = payload.get("settings", [])

    settings = [DocumentAccessSettingCreate(**s) for s in raw_settings]
    return service.bulk_save(target_user_id, target_department_id, settings, str(session.user_id))


# ── Справочник блоков по типам документов ────────────────────────────────────

@document_access_settings_router.get(
    "/meta/blocks",
    status_code=status.HTTP_200_OK,
    summary="Список доступных блоков по типам документов",
)
def get_blocks_meta(
    _session=Depends(get_session),
):
    from app.models.document_access_setting import BLOCKS_BY_TYPE
    return BLOCKS_BY_TYPE
