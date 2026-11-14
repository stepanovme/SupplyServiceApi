from sqlalchemy.orm import Session

from app.models.project_user_role_template import ProjectUserRoleTemplate


class ProjectUserRoleTemplateRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(self) -> list[ProjectUserRoleTemplate]:
        return self.db.query(ProjectUserRoleTemplate).all()

    def get_by_id(self, item_id: int) -> ProjectUserRoleTemplate | None:
        return self.db.query(ProjectUserRoleTemplate).filter(ProjectUserRoleTemplate.id == item_id).first()

    def create(self, item: ProjectUserRoleTemplate) -> ProjectUserRoleTemplate:
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def save(self, item: ProjectUserRoleTemplate) -> ProjectUserRoleTemplate:
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete(self, item: ProjectUserRoleTemplate) -> None:
        self.db.delete(item)
        self.db.commit()
