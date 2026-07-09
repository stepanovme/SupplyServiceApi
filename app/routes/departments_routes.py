from fastapi import APIRouter, Depends, status

from app.database import DbAuthSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.department import DepartmentCreate, DepartmentUpdate, DepartmentUserCreate, DepartmentUserUpdate
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.department_repository import DepartmentRepository
from app.services.department_service import DepartmentService

departments_router = APIRouter(prefix="/departments", tags=["Departments"])


def build_service(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession | None = None,
) -> DepartmentService:
    auth_repo = AuthUserRepository(auth_db) if auth_db else None
    return DepartmentService(DepartmentRepository(supply_db), auth_repo)


# --- Department ---

@departments_router.get("", status_code=status.HTTP_200_OK)
def get_all(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).get_all()


@departments_router.get("/my", status_code=status.HTTP_200_OK)
def get_my(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).get_my(_session.user_id)


@departments_router.get("/{dept_id}", status_code=status.HTTP_200_OK)
def get_by_id(
    dept_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).get_by_id(dept_id)


@departments_router.post("", status_code=status.HTTP_201_CREATED)
def create(
    payload: DepartmentCreate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).create(payload, _session.user_id)


@departments_router.patch("/{dept_id}", status_code=status.HTTP_200_OK)
def update(
    dept_id: int,
    payload: DepartmentUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).update(dept_id, payload, _session.user_id)


@departments_router.delete("/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    dept_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete(dept_id)
    return None


# --- DepartmentUser ---

@departments_router.get("/{departament_id}/users", status_code=status.HTTP_200_OK)
def get_users(
    departament_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).get_users_by_department(departament_id)


@departments_router.post("/{departament_id}/users", status_code=status.HTTP_201_CREATED)
def create_user(
    departament_id: int,
    payload: DepartmentUserCreate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).create_user(payload, _session.user_id)


@departments_router.patch("/users/{membership_id}", status_code=status.HTTP_200_OK)
def update_user(
    membership_id: str,
    payload: DepartmentUserUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).update_user(membership_id, payload)


@departments_router.delete("/users/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    membership_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete_user(membership_id)
    return None
