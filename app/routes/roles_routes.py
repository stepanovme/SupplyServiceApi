from fastapi import APIRouter, Depends, HTTPException, status

from app.database import DbAuthSession, DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.role import (
    AssignDepartmentRole,
    AssignUserRole,
    RoleCreate,
    RoleUpdate,
)
from app.repositories.department_repository import DepartmentRepository
from app.repositories.role_repository import (
    DepartmentRoleRepository,
    RolePermissionRepository,
    RoleRepository,
    UserRoleRepository,
)
from app.services.role_service import RoleService

roles_router = APIRouter(prefix="/roles", tags=["Roles"])


def build_role_service(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession | None = None,
    reference_db: DbReferenceSession | None = None,
) -> RoleService:
    return RoleService(
        RoleRepository(supply_db),
        RolePermissionRepository(supply_db),
        UserRoleRepository(supply_db),
        DepartmentRoleRepository(supply_db),
        DepartmentRepository(supply_db),
    )


# ── Roles CRUD ─────────────────────────────────────────

@roles_router.get("", status_code=status.HTTP_200_OK)
def get_roles(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
    active_only: bool = True,
):
    service = build_role_service(supply_db)
    return service.get_all(active_only)


@roles_router.get("/{role_id}", status_code=status.HTTP_200_OK)
def get_role(
    role_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_role_service(supply_db)
    return service.get_by_id(role_id)


@roles_router.post("", status_code=status.HTTP_201_CREATED)
def create_role(
    payload: RoleCreate,
    supply_db: DbSupplySession,
    session=Depends(get_session),
):
    service = build_role_service(supply_db)
    return service.create(payload, str(session.user_id))


@roles_router.patch("/{role_id}", status_code=status.HTTP_200_OK)
def update_role(
    role_id: str,
    payload: RoleUpdate,
    supply_db: DbSupplySession,
    session=Depends(get_session),
):
    service = build_role_service(supply_db)
    return service.update(role_id, payload, str(session.user_id))


@roles_router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_role_service(supply_db)
    service.delete(role_id)
    return None


# ── Permissions ────────────────────────────────────────

@roles_router.get("/{role_id}/permissions", status_code=status.HTTP_200_OK)
def get_permissions(
    role_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_role_service(supply_db)
    return service.get_permissions(role_id)


@roles_router.put("/{role_id}/permissions", status_code=status.HTTP_200_OK)
def update_permissions(
    role_id: str,
    payload: dict,
    supply_db: DbSupplySession,
    session=Depends(get_session),
):
    service = build_role_service(supply_db)
    return service.update_permissions(role_id, payload, str(session.user_id))


@roles_router.delete("/{role_id}/permissions", status_code=status.HTTP_204_NO_CONTENT)
def delete_permissions(
    role_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_role_service(supply_db)
    service.delete_permissions(role_id)
    return None


# ── User roles ─────────────────────────────────────────

@roles_router.get("/users/{user_id}/roles", status_code=status.HTTP_200_OK)
def get_user_roles(
    user_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_role_service(supply_db)
    return service.get_user_roles(user_id)


@roles_router.post("/users/{user_id}/roles", status_code=status.HTTP_201_CREATED)
def assign_user_role(
    user_id: str,
    payload: AssignUserRole,
    supply_db: DbSupplySession,
    session=Depends(get_session),
):
    service = build_role_service(supply_db)
    return service.assign_user_role(user_id, payload, str(session.user_id))


@roles_router.delete("/users/{user_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_user_role(
    user_id: str,
    role_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_role_service(supply_db)
    service.remove_user_role(user_id, role_id)
    return None


# ── Department roles ──────────────────────────────────

@roles_router.get("/departments/{department_id}/roles", status_code=status.HTTP_200_OK)
def get_department_roles(
    department_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_role_service(supply_db)
    return service.get_department_roles(department_id)


@roles_router.post("/departments/{department_id}/roles", status_code=status.HTTP_201_CREATED)
def assign_department_role(
    department_id: int,
    payload: AssignDepartmentRole,
    supply_db: DbSupplySession,
    session=Depends(get_session),
):
    service = build_role_service(supply_db)
    return service.assign_department_role(department_id, payload, str(session.user_id))


@roles_router.delete("/departments/{department_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_department_role(
    department_id: int,
    role_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    service = build_role_service(supply_db)
    service.remove_department_role(department_id, role_id)
    return None


# ── Check permissions ─────────────────────────────────

@roles_router.get("/check/requests", status_code=status.HTTP_200_OK)
def check_request_permission(
    user_id: str,
    department_ids: list[int],
    permission: str,
    supply_db: DbSupplySession,
):
    service = build_role_service(supply_db)
    return service.check_request_permission(user_id, department_ids, permission)


@roles_router.get("/check/objects", status_code=status.HTTP_200_OK)
def check_object_permission(
    user_id: str,
    department_ids: list[int],
    permission: str,
    supply_db: DbSupplySession,
):
    service = build_role_service(supply_db)
    return service.check_object_permission(user_id, department_ids, permission)