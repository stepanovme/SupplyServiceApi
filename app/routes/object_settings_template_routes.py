from fastapi import APIRouter, Depends, status

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.object_settings_template import ObjectSettingsTemplateCreate, ObjectSettingsTemplateUpdate
from app.repositories.object_settings_template_repository import ObjectSettingsTemplateRepository
from app.services.object_settings_template_service import ObjectSettingsTemplateService

object_settings_template_router = APIRouter(
    prefix="/object-settings-template", tags=["ObjectSettingsTemplate"]
)


@object_settings_template_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Получить список шаблонов настроек объектов",
)
def get_all_templates(
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = ObjectSettingsTemplateService(ObjectSettingsTemplateRepository(db))
    return service.get_all()


@object_settings_template_router.get(
    "/{item_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить шаблон настройки объекта по ID",
)
def get_template_by_id(
    item_id: str,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = ObjectSettingsTemplateService(ObjectSettingsTemplateRepository(db))
    return service.get_by_id(item_id)


@object_settings_template_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать шаблон настройки объекта",
)
def create_template(
    data: ObjectSettingsTemplateCreate,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = ObjectSettingsTemplateService(ObjectSettingsTemplateRepository(db))
    return service.create(data)


@object_settings_template_router.patch(
    "/{item_id}",
    status_code=status.HTTP_200_OK,
    summary="Обновить шаблон настройки объекта",
)
def update_template(
    item_id: str,
    data: ObjectSettingsTemplateUpdate,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = ObjectSettingsTemplateService(ObjectSettingsTemplateRepository(db))
    return service.update(item_id, data)


@object_settings_template_router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить шаблон настройки объекта",
)
def delete_template(
    item_id: str,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = ObjectSettingsTemplateService(ObjectSettingsTemplateRepository(db))
    service.delete(item_id)
