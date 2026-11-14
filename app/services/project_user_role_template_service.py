from fastapi import HTTPException, status

from app.models.project_user_role_template import (
    ProjectUserRoleTemplate,
    ProjectUserRoleTemplateCreate,
    ProjectUserRoleTemplateUpdate,
)
from app.repositories.project_user_role_template_repository import (
    ProjectUserRoleTemplateRepository,
)


class ProjectUserRoleTemplateService:
    def __init__(self, repo: ProjectUserRoleTemplateRepository) -> None:
        self.repo = repo

    def get_all(self) -> list[ProjectUserRoleTemplate]:
        return self.repo.get_all()

    def get_by_id(self, item_id: int) -> ProjectUserRoleTemplate:
        item = self.repo.get_by_id(item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template role not found",
            )
        return item

    def create(self, data: ProjectUserRoleTemplateCreate) -> ProjectUserRoleTemplate:
        item = ProjectUserRoleTemplate(**data.model_dump())
        return self.repo.create(item)

    def update(
        self, item_id: int, data: ProjectUserRoleTemplateUpdate
    ) -> ProjectUserRoleTemplate:
        item = self.get_by_id(item_id)
        update_data = data.model_dump(exclude_none=True)
        for key, value in update_data.items():
            setattr(item, key, value)
        return self.repo.save(item)

    def delete(self, item_id: int) -> None:
        item = self.get_by_id(item_id)
        self.repo.delete(item)
