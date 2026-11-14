from fastapi import APIRouter, Depends, HTTPException, status

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.project_user_role_template import (
    ProjectUserRoleTemplateCreate,
    ProjectUserRoleTemplateUpdate,
)
from app.repositories.project_user_role_template_repository import (
    ProjectUserRoleTemplateRepository,
)
from app.services.project_user_role_template_service import (
    ProjectUserRoleTemplateService,
)

project_user_roles_template_router = APIRouter(
    prefix="/project-user-roles-template", tags=["ProjectUserRolesTemplate"]
)


@project_user_roles_template_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Получить список шаблонов ролей",
)
def get_all_templates(
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = ProjectUserRoleTemplateService(ProjectUserRoleTemplateRepository(db))
    return service.get_all()


@project_user_roles_template_router.get(
    "/{item_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить шаблон роли по ID",
)
def get_template_by_id(
    item_id: int,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = ProjectUserRoleTemplateService(ProjectUserRoleTemplateRepository(db))
    return service.get_by_id(item_id)


@project_user_roles_template_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать шаблон роли",
)
def create_template(
    data: ProjectUserRoleTemplateCreate,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = ProjectUserRoleTemplateService(ProjectUserRoleTemplateRepository(db))
    return service.create(data)


@project_user_roles_template_router.patch(
    "/{item_id}",
    status_code=status.HTTP_200_OK,
    summary="Обновить шаблон роли",
)
def update_template(
    item_id: int,
    data: ProjectUserRoleTemplateUpdate,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = ProjectUserRoleTemplateService(ProjectUserRoleTemplateRepository(db))
    return service.update(item_id, data)


@project_user_roles_template_router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить шаблон роли",
)
def delete_template(
    item_id: int,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = ProjectUserRoleTemplateService(ProjectUserRoleTemplateRepository(db))
    service.delete(item_id)
