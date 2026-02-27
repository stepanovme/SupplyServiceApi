from fastapi import APIRouter, Depends, status

from app.database import DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.session import SessionDB
from app.repositories.project_repository import ProjectRepository
from app.repositories.project_user_role_repository import ProjectUserRoleRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.services.request_object_service import RequestObjectService

request_objects_router = APIRouter(prefix="/request-objects", tags=["RequestObjects"])


@request_objects_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Получить список всех объектов заявок",
)
def get_all_request_objects(
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    service = RequestObjectService(
        ReferenceObjectRepository(reference_db),
        ProjectUserRoleRepository(supply_db),
        ProjectRepository(supply_db),
    )
    return service.get_all()


@request_objects_router.get(
    "/my",
    status_code=status.HTTP_200_OK,
    summary="Получить список доступных мне объектов заявок",
)
def get_my_request_objects(
    supply_db: DbSupplySession,
    reference_db: DbReferenceSession,
    session: SessionDB = Depends(get_session),
):
    service = RequestObjectService(
        ReferenceObjectRepository(reference_db),
        ProjectUserRoleRepository(supply_db),
        ProjectRepository(supply_db),
    )
    return service.get_available_for_user(str(session.user_id))
