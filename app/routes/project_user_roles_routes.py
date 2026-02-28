from fastapi import APIRouter, Depends, HTTPException, status

from app.database import DbAuthSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.project_user_role import ProjectUserRoleCreate, ProjectUserRoleType
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.project_user_role_repository import ProjectUserRoleRepository
from app.services.project_user_role_service import ProjectUserRoleService

project_user_roles_router = APIRouter(prefix="/project-user-roles", tags=["ProjectUserRoles"])


@project_user_roles_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Получить список ролей пользователей объектов",
)
def get_all_project_user_roles(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    service = ProjectUserRoleService(
        ProjectUserRoleRepository(supply_db),
        AuthUserRepository(auth_db),
    )
    return service.get_all_with_users()


@project_user_roles_router.get(
    "/{object_levels_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить роли пользователей по object_levels_id",
)
def get_project_user_roles_by_object_level(
    object_levels_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    role: ProjectUserRoleType | None = None,
    _session=Depends(get_session),
):
    service = ProjectUserRoleService(
        ProjectUserRoleRepository(supply_db),
        AuthUserRepository(auth_db),
    )
    role_value = role.value if role else None
    return service.get_by_object_levels_id_with_users(object_levels_id, role_value)


@project_user_roles_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Добавить роль пользователя к объекту",
)
def create_project_user_role(
    payload: ProjectUserRoleCreate,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = ProjectUserRoleService(ProjectUserRoleRepository(db))
    return service.create(payload)


@project_user_roles_router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить роль пользователя у объекта",
)
def delete_project_user_role(
    item_id: str,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = ProjectUserRoleService(ProjectUserRoleRepository(db))
    deleted = service.delete(item_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return None
