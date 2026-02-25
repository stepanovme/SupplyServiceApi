from sqlalchemy.orm import Session

from app.models.project_user_role import ProjectUserRole


class ProjectUserRoleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(self) -> list[ProjectUserRole]:
        return self.db.query(ProjectUserRole).all()

    def create(self, item: ProjectUserRole) -> ProjectUserRole:
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_by_id(self, item_id: str) -> ProjectUserRole | None:
        return self.db.query(ProjectUserRole).filter(ProjectUserRole.id == item_id).first()

    def delete(self, item: ProjectUserRole) -> None:
        self.db.delete(item)
        self.db.commit()
