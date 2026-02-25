from app.models.project import Project, ProjectCreate, ProjectUpdate
from app.repositories.project_repository import ProjectRepository


class ProjectService:
    def __init__(self, repo: ProjectRepository) -> None:
        self.repo = repo

    def get_all(self) -> list[Project]:
        return self.repo.get_all()

    def create(self, data: ProjectCreate) -> Project:
        project_data = data.model_dump(exclude_none=True)
        project = Project(**project_data)
        return self.repo.create(project)

    def update(self, project_id: str, data: ProjectUpdate) -> Project | None:
        project = self.repo.get_by_id(project_id)
        if not project:
            return None

        update_data = data.model_dump(exclude_none=True)
        for key, value in update_data.items():
            setattr(project, key, value)

        return self.repo.save(project)
