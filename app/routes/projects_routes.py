from fastapi import APIRouter, Depends, HTTPException, status

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.project import ProjectCreate, ProjectUpdate
from app.repositories.project_repository import ProjectRepository
from app.services.project_service import ProjectService

projects_router = APIRouter(prefix="/projects", tags=["Projects"])


@projects_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Получить список объектов",
)
def get_all_projects(db: DbSupplySession, _session=Depends(get_session)):
    service = ProjectService(ProjectRepository(db))
    return service.get_all()


@projects_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать объект",
)
def create_project(
    project_data: ProjectCreate,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = ProjectService(ProjectRepository(db))
    return service.create(project_data)


@projects_router.patch(
    "/{project_id}",
    status_code=status.HTTP_200_OK,
    summary="Редактировать объект",
)
def update_project(
    project_id: str,
    project_data: ProjectUpdate,
    db: DbSupplySession,
    _session=Depends(get_session),
):
    service = ProjectService(ProjectRepository(db))
    updated = service.update(project_id, project_data)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return updated
