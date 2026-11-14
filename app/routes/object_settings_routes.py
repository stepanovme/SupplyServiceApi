from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.database import DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.object_setting import ObjectSettingCreate, ObjectSettingUpdate
from app.repositories.department_repository import DepartmentRepository
from app.repositories.object_setting_repository import ObjectSettingRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.repositories.role_repository import (
    DepartmentRoleRepository,
    RolePermissionRepository,
    RoleRepository,
    UserRoleRepository,
)
from app.services.object_setting_service import ObjectSettingService
from app.services.role_service import RoleService

object_settings_router = APIRouter(prefix="/object-settings", tags=["ObjectSettings"])


@object_settings_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Получить список настроек объектов",
)
def get_all_object_settings(
    db: DbSupplySession,
    _session=Depends(get_session),
    object_id: str | None = Query(default=None),
):
    service = ObjectSettingService(ObjectSettingRepository(db))
    if object_id:
        return service.repo.get_by_object_id(object_id)
    return service.get_all()


@object_settings_router.get(
    "/by-object/{object_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить настройки по object_id",
)
def get_object_settings_by_object(
    object_id: str,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = ObjectSettingService(ObjectSettingRepository(db))
    return service.repo.get_by_object_id(object_id)


@object_settings_router.get(
    "/approve-request-users",
    status_code=status.HTTP_200_OK,
    summary="Пользователи с ролью approve_request по объекту",
)
def get_approve_request_users(
    db: DbSupplySession,
    _session=Depends(get_session),
    object_id: str = Query(...),
):
    repo = ObjectSettingRepository(db)
    return repo.get_approve_request_users(object_id)


@object_settings_router.get(
    "/my/create-request",
    status_code=status.HTTP_200_OK,
    summary="Объекты, в которых я указан с ролью create_request",
)
def get_my_create_request_objects(
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    user_id = _session.user_id
    object_ids = ObjectSettingService(ObjectSettingRepository(db)).get_create_request_object_ids(user_id)
    if not object_ids:
        return []
    objects = ReferenceObjectRepository(reference_db).get_objects_by_ids(list(object_ids))
    return [
        {"object_id": obj.id, "short_name": obj.short_name, "full_name": obj.full_name}
        for obj in objects
    ]


@object_settings_router.get(
    "/my/create-request-available",
    status_code=status.HTTP_200_OK,
    summary="Объекты доступные для создания заявок (с учётом исключений из RBAC)",
)
def get_my_create_request_available_objects(
    db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    user_id = _session.user_id

    dept_repo = DepartmentRepository(db)
    dept_ids = dept_repo.get_department_ids_for_user(user_id)

    role_repo = RoleRepository(db)
    perm_repo = RolePermissionRepository(db)
    user_role_repo = UserRoleRepository(db)
    dept_role_repo = DepartmentRoleRepository(db)
    role_service = RoleService(role_repo, perm_repo, user_role_repo, dept_role_repo)

    settings = role_service.get_create_request_effective_settings(user_id, dept_ids)

    obj_setting_service = ObjectSettingService(ObjectSettingRepository(db))
    ref_repo = ReferenceObjectRepository(reference_db)

    if settings:
        create_setting = settings.get("create")
        create_except = settings.get("create_except") or []

        if create_setting == "all" and create_except:
            all_objects = ref_repo.get_objects_except_ids(create_except)
            return [
                {"object_id": obj.id, "short_name": obj.short_name, "full_name": obj.full_name}
                for obj in all_objects
            ]

        if create_setting == "all":
            all_objects = ref_repo.get_all_objects()
            return [
                {"object_id": obj.id, "short_name": obj.short_name, "full_name": obj.full_name}
                for obj in all_objects
            ]

        if create_setting == "all_except":
            all_objects = ref_repo.get_objects_except_ids(create_except)
            return [
                {"object_id": obj.id, "short_name": obj.short_name, "full_name": obj.full_name}
                for obj in all_objects
            ]

    object_ids = obj_setting_service.get_create_request_object_ids(user_id)
    if not object_ids:
        return []
    objects = ref_repo.get_objects_by_ids(list(object_ids))
    return [
        {"object_id": obj.id, "short_name": obj.short_name, "full_name": obj.full_name}
        for obj in objects
    ]


@object_settings_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать настройку объекта",
)
def create_object_setting(
    data: ObjectSettingCreate,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = ObjectSettingService(ObjectSettingRepository(db))
    return service.create(data)


@object_settings_router.get(
    "/{item_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить настройку объекта по ID",
)
def get_object_setting_by_id(
    item_id: str,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = ObjectSettingService(ObjectSettingRepository(db))
    return service.get_by_id(item_id)


@object_settings_router.patch(
    "/{item_id}",
    status_code=status.HTTP_200_OK,
    summary="Обновить настройку объекта",
)
def update_object_setting(
    item_id: str,
    data: ObjectSettingUpdate,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = ObjectSettingService(ObjectSettingRepository(db))
    return service.update(item_id, data)


@object_settings_router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить настройку объекта",
)
def delete_object_setting(
    item_id: str,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = ObjectSettingService(ObjectSettingRepository(db))
    service.delete(item_id)
